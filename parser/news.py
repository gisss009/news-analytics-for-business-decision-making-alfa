"""Выгрузка деловых новостей через pyfinews и раскладка по темам.

pyfinews ходит в Google News RSS. Своей ленты и языковой модели здесь нет:
тема назначается запросом, которым новость нашли, и словарём из topics.py.
"""

from __future__ import annotations

import re
from urllib.parse import urlencode

from pyfinews import NewsClient
from pyfinews.exceptions import PyfinewsError
from pyfinews.models import NewsArticle
from pyfinews.queries.google_news import GoogleNewsQuery

from parser.bank import Skip
from parser.schema import SourceAnchor, Statement, card_from_pyfinews
from parser.topics import TOPICS, classify

_TITLE_KEY = re.compile(r"[^\w]+", re.UNICODE)
_CYRILLIC = re.compile(r"[а-яё]", re.IGNORECASE)
_NOISE = re.compile(
    r"пособи|tesla|cybercab|черногор|севастопол|ревд|бурят|пензен|хакаси|"
    r"vietnam|вьетнам|винодел|\bвина\b|почт|безработиц|водоканал|"
    r"школьник|мастер-класс|мастер-лекц|ножки буша|бепешк",
    re.IGNORECASE,
)
_GOOGLE_NEWS = "https://news.google.com/rss/search"

# Запросы ленты «Новости»: бизнес и экономика, не общий мусор Google News.
BUSINESS_QUERIES: tuple[tuple[str, str], ...] = (
    ("Экономика", "экономика России"),
    ("Компании", "крупные российские компании"),
    ("Рынки", "Мосбиржа акции компаний"),
    ("Ключевая ставка", "ключевая ставка Банк России"),
    ("Валютные курсы", "курс рубля к доллару"),
    ("Сырьё", "цена нефти Brent"),
    ("Инфляция", "инфляция Росстат"),
    ("Внешняя торговля", "экспорт российских компаний"),
)


def fetch_news(
    *,
    hours: float = 168,
    per_topic: int = 4,
    search=None,
    retrieved_at: str | None = None,
):
    """Возвращает карточки и пропуски. search подменяется в тестах."""

    if search is None:
        search = _live_search

    grouped: dict[str, dict] = {}
    skipped: list[Skip] = []
    for topic in TOPICS:
        try:
            articles = search(topic.query, hours=hours, max_articles=per_topic)
        except (PyfinewsError, TimeoutError, OSError) as exc:
            skipped.append(Skip(topic.query, str(exc)))
            continue
        for article in articles:
            if not isinstance(article, NewsArticle):
                skipped.append(Skip(topic.query, "pyfinews вернул не статью"))
                continue
            key = _title_key(article.title)
            current = grouped.get(key)
            if current is None:
                grouped[key] = {"article": article, "hints": [topic.label]}
                continue
            if topic.label not in current["hints"]:
                current["hints"].append(topic.label)
            if len(article.summary or "") > len(current["article"].summary or ""):
                current["article"] = article

    cards = []
    for item in grouped.values():
        article = item["article"]
        record = {
            "title": article.title,
            "url": article.url,
            "resolved_url": article.resolved_url,
            "source": article.source,
            "published_at": article.published_at,
            "retrieved_at": article.retrieved_at,
            "summary": article.summary,
            "text": article.text,
        }
        card = card_from_pyfinews(record, retrieved_at=retrieved_at)
        card.topics, card.industries = classify(card.title, card.text, hinted=item["hints"])
        if card.text and re.search(r"\d", card.text):
            card.facts = [
                Statement(card.text[:280], SourceAnchor(kind="url", url=card.anchor.url))
            ]
        cards.append(card)
    cards.sort(key=lambda card: card.published_at or "", reverse=True)
    return cards, skipped


def fetch_business_news(
    *,
    hours: float = 72,
    per_query: int = 5,
    search=None,
    retrieved_at: str | None = None,
):
    """Деловая лента: экономика и компании. Мусор вроде пособий США сюда не входит."""

    if search is None:
        search = _live_search

    grouped: dict[str, dict] = {}
    skipped: list[Skip] = []
    for label, query in BUSINESS_QUERIES:
        try:
            articles = search(query, hours=hours, max_articles=per_query)
        except (PyfinewsError, TimeoutError, OSError) as exc:
            skipped.append(Skip(query, str(exc)))
            continue
        for article in articles:
            if not isinstance(article, NewsArticle):
                skipped.append(Skip(query, "pyfinews вернул не статью"))
                continue
            if _is_noise(article.title):
                continue
            key = _title_key(article.title)
            current = grouped.get(key)
            if current is None:
                grouped[key] = {"article": article, "hints": [label]}
                continue
            if label not in current["hints"]:
                current["hints"].append(label)
            if len(article.summary or "") > len(current["article"].summary or ""):
                current["article"] = article

    cards = []
    for item in grouped.values():
        article = item["article"]
        record = {
            "title": article.title,
            "url": article.url,
            "resolved_url": article.resolved_url,
            "source": article.source,
            "published_at": article.published_at,
            "retrieved_at": article.retrieved_at,
            "summary": article.summary,
            "text": article.text,
        }
        card = card_from_pyfinews(record, retrieved_at=retrieved_at)
        card.topics, card.industries = classify(card.title, card.text, hinted=item["hints"])
        cards.append(card)
    cards.sort(key=lambda card: card.published_at or "", reverse=True)
    return cards, skipped


def _is_noise(title: str) -> bool:
    if len(_CYRILLIC.findall(title or "")) < 12:
        return True
    return _NOISE.search(title or "") is not None


def _live_search(query: str, *, hours: float, max_articles: int) -> list[NewsArticle]:
    original = GoogleNewsQuery.to_url

    def russian_edition(self) -> str:
        return f"{_GOOGLE_NEWS}?{urlencode({'q': self.query, 'hl': 'ru', 'gl': 'RU', 'ceid': 'RU:ru'})}"

    GoogleNewsQuery.to_url = russian_edition
    try:
        with NewsClient(timeout=15) as client:
            return client.search(
                query,
                hours=hours,
                max_articles=max_articles,
                resolve_urls=False,
                show_progress=False,
            )
    finally:
        GoogleNewsQuery.to_url = original


def _title_key(title: str) -> str:
    return _TITLE_KEY.sub(" ", title.casefold()).strip()
