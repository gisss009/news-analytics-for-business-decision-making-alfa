"""PyfinewsSource без сети: поиск pyfinews и страницы издателей подменены образцами."""
import socket
from datetime import datetime, timezone

import httpx
import pytest
from pyfinews.models import NewsArticle

from app.ingest.sources.pyfinews_source import QUERIES, PyfinewsSource, clean_title, is_noise

WHEN = datetime(2026, 10, 23, 10, 50, tzinfo=timezone.utc)
ARTICLE_HTML = """<html><head><title>ЦБ сохранил ставку</title></head><body><article>
<h1>ЦБ РФ сохранил ключевую ставку на уровне 14%</h1>
<p>Совет директоров Банка России 23 октября 2026 года сохранил ключевую ставку на уровне 14% годовых.
Регулятор отметил, что инфляционные ожидания остаются повышенными, а кредитование растёт быстрее прогноза.</p>
<p>Следующее заседание по ставке пройдёт 18 декабря 2026 года. Аналитики ожидают сохранения жёсткой политики.</p>
</article></body></html>"""


def article(title, source, url, summary=None):
    return NewsArticle(title=f"{title} - {source}", url=f"https://news.google.com/rss/articles/{url}", source=source,
                       published_at=WHEN, retrieved_at=WHEN, summary=summary, resolved_url=f"https://{url}")


def sample_search(query, hours, max_articles):
    if query.startswith("ключевая ставка"):
        return [article("ЦБ РФ сохранил ключевую ставку на уровне 14%", "Интерфакс", "example.org/cbr"),
                article("ЦБ РФ сохранил ключевую ставку на уровне 14%", "Интерфакс", "example.org/cbr-copy"),
                article("Число заявок на пособие по безработице в США упало", "Финансы", "example.org/us")]
    if query.startswith("курс доллара"):
        raise TimeoutError("RSS не ответил")
    if query.startswith("инфляция"):
        return [article("ЦБ РФ сохранил ключевую ставку на уровне 14%", "Интерфакс", "example.org/cbr"),
                article("Росстат: недельная инфляция замедлилась до 0,05%", "РБК", "example.org/infl")]
    return []


def publisher(request: httpx.Request):
    if request.url.host == "example.org" and request.url.path == "/cbr":
        return httpx.Response(200, text=ARTICLE_HTML)
    return httpx.Response(404)


@pytest.fixture
def no_network(monkeypatch):
    def deny(*a, **k):
        raise OSError("сеть запрещена в тесте")
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket.socket, "connect", deny)


def source():
    return PyfinewsSource(search=sample_search, transport=httpx.MockTransport(publisher), pause_s=0)


def test_links_dedup_noise_and_errors(no_network):
    src = source()
    links = src.fetch_list()
    titles = [link.title for link in links]
    assert "ЦБ РФ сохранил ключевую ставку на уровне 14%" in titles
    assert not any("пособие" in t for t in titles)
    assert len(titles) == len(set(titles)) == 2
    assert len(src.errors) == 1 and "RSS не ответил" in src.errors[0]
    assert all(link.published_at.tzinfo is not None for link in links)


def test_article_full_text_and_title_fallback(no_network):
    src = source()
    links = {link.title: link for link in src.fetch_list()}
    full = src.fetch_article(links["ЦБ РФ сохранил ключевую ставку на уровне 14%"])
    assert full.text_status == "full" and "23 октября 2026 года" in full.text and full.url == "https://example.org/cbr"
    assert full.topic_hint == "rate" and full.source_name == "Интерфакс" and not full.synthetic
    assert full.item_id.startswith("w_") and full.published_at == WHEN
    fallback = src.fetch_article(links["Росстат: недельная инфляция замедлилась до 0,05%"])
    assert fallback.text_status == "title_only" and fallback.text == fallback.title


def test_helpers():
    assert clean_title("Ставка 14% - РБК", "РБК") == "Ставка 14%"
    assert is_noise("Tesla представила Cybercab") and is_noise("short")
    assert len(QUERIES) >= 10
