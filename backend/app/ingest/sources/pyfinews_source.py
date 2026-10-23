"""Живые деловые новости через pyfinews (Google News RSS, русская редакция).

Основано на parser/news.py и parser/topics.py из ветки frontend: запросы по темам, отсев шума, объединение
одинаковых заголовков, подсказка темы от запроса. Отличия: работает за интерфейсом Source; текст статьи
скачивается со страницы издателя (httpx + trafilatura), при неудаче остаётся заголовок с пометкой.
Текст новостей — данные, а не инструкции: в промпты он попадает только через data_block().
Условия использования источников: docs/sources.md.
"""
import hashlib
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape
from typing import Callable
from urllib.parse import urlencode

import httpx

from app.core.logging import get_logger
from app.ingest.sources.base import Link, RawArticle, Source

log = get_logger("sources.pyfinews")

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
USER_AGENT = "Mozilla/5.0 (compatible; news-analytics-prototype/0.1; hackathon research)"

# (запрос в pyfinews, тема нашего классификатора) — запросы взяты из parser/topics.py
QUERIES: tuple[tuple[str, str], ...] = (
    ("ключевая ставка Банк России", "rate"),
    ("инфляция в России", "inflation"),
    ("курс доллара к рублю", "fx"),
    ("цены на нефть и золото", "commodities"),
    ("доходность ОФЗ", "capital_markets"),
    ("санкции против России", "sanctions_trade"),
    ("экспортные пошлины России", "regulation"),
    ("розничные продажи в России", "industry"),
    ("логистика и фрахт", "industry"),
    ("экспорт и импорт России", "sanctions_trade"),
    ("тарифы на электроэнергию", "regulation"),
)
# заголовки не по теме деловой ленты (из parser/news.py) и слишком короткие/нерусские
NOISE = re.compile(
    r"пособи|tesla|cybercab|черногор|севастопол|ревд|бурят|пензен|хакаси|vietnam|вьетнам|винодел|\bвина\b|почт|"
    r"водоканал|школьник|мастер-класс|мастер-лекц|ножки буша|бепешк", re.I)
CYRILLIC = re.compile(r"[а-яё]", re.I)
TAG = re.compile(r"<[^>]+>")
TITLE_KEY = re.compile(r"[^\w]+", re.U)

SearchFn = Callable[[str, float, int], list]


def is_noise(title: str) -> bool:
    return len(CYRILLIC.findall(title or "")) < 12 or NOISE.search(title or "") is not None


def clean_title(title: str, source: str | None) -> str:
    """Google News добавляет « - Издание» в конец заголовка."""
    t = title.strip()
    if source and t.endswith(f" - {source}"):
        t = t[: -len(source) - 3].rstrip()
    return t


def plain(text: str | None) -> str:
    return re.sub(r"\s+", " ", unescape(TAG.sub(" ", text or ""))).strip()


def item_id_for(url: str) -> str:
    return "w_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def live_search(query: str, hours: float, max_articles: int) -> list:
    """Поиск pyfinews в русской редакции Google News с раскрытием ссылок на издателя."""
    from pyfinews import NewsClient
    from pyfinews.queries.google_news import GoogleNewsQuery

    original = GoogleNewsQuery.to_url
    GoogleNewsQuery.to_url = lambda self: f"{GOOGLE_NEWS_RSS}?{urlencode({'q': self.query, 'hl': 'ru', 'gl': 'RU', 'ceid': 'RU:ru'})}"
    try:
        with NewsClient(timeout=15) as client:
            return client.search(query, hours=hours, max_articles=max_articles, resolve_urls=True, show_progress=False)
    finally:
        GoogleNewsQuery.to_url = original


@dataclass
class _Found:
    article: object
    hints: list[str] = field(default_factory=list)


class PyfinewsSource(Source):
    name = "pyfinews"

    def __init__(self, hours: float = 72, per_topic: int = 4, search: SearchFn | None = None,
                 transport: httpx.BaseTransport | None = None, fetch_text: bool = True, pause_s: float = 0.3):
        self.hours, self.per_topic = hours, per_topic
        self._search = search or live_search
        self._transport, self._fetch_text, self._pause = transport, fetch_text, pause_s
        self._found: dict[str, _Found] = {}
        self.errors: list[str] = []

    def fetch_list(self, since: datetime | None = None) -> list[Link]:
        by_title: dict[str, _Found] = {}
        for query, topic in QUERIES:
            try:
                articles = self._search(query, self.hours, self.per_topic)
            except Exception as e:  # noqa: BLE001 — сбой одного запроса не останавливает остальные
                self.errors.append(f"{query}: {type(e).__name__}: {str(e)[:120]}")
                log.warning("pyfinews_query_failed", extra={"query": query, "error": str(e)[:200]})
                continue
            for a in articles:
                title = clean_title(a.title, a.source)
                if is_noise(title):
                    continue
                key = TITLE_KEY.sub(" ", title.casefold()).strip()
                found = by_title.setdefault(key, _Found(a))
                if topic not in found.hints:
                    found.hints.append(topic)
        links = []
        for f in by_title.values():
            a = f.article
            published = (a.published_at or a.retrieved_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
            if since and published <= since:
                continue
            url = a.resolved_url or a.url
            self._found[url] = f
            links.append(Link(url=url, title=clean_title(a.title, a.source), published_at=published))
        return sorted(links, key=lambda link: link.published_at, reverse=True)

    def _download_text(self, url: str) -> str | None:
        if not self._fetch_text or "news.google.com" in url:
            return None
        import trafilatura
        try:
            with httpx.Client(timeout=15, follow_redirects=True, transport=self._transport,
                              headers={"User-Agent": USER_AGENT}) as http:
                r = http.get(url)
            if r.status_code != 200:
                return None
            text = trafilatura.extract(r.text, include_comments=False, include_tables=False) or None
            return text[:6000] if text else None
        except Exception as e:  # noqa: BLE001 — страница издателя недоступна: остаётся заголовок
            log.warning("article_download_failed", extra={"url": url[:120], "error": str(e)[:200]})
            return None
        finally:
            if self._pause:
                time.sleep(self._pause)

    def fetch_article(self, link: Link) -> RawArticle:
        f = self._found[link.url]
        a = f.article
        title = clean_title(a.title, a.source)
        body = self._download_text(link.url)
        summary = plain(a.summary)
        if body:
            text, status = body, "full"
        elif summary and summary.lower() != title.lower() and len(summary) > len(title) + 20:
            text, status = summary, "summary"
        else:
            text, status = title, "title_only"
        if not text.startswith(title[:40]):
            text = f"{title}. {text}" if status != "title_only" else text
        return RawArticle(item_id=item_id_for(link.url), url=link.url, title=title, text=text,
                          published_at=link.published_at, source_name=a.source or "Google News",
                          source_type="news", synthetic=False, holdout=False,
                          topic_hint=f.hints[0] if f.hints else None, text_status=status)
