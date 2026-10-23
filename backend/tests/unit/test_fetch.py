import socket
from datetime import datetime, timezone

import httpx
import pytest

from app.core.db import connect
from app.ingest import classify, fetch
from app.ingest.sources.base import Link, RawArticle, Source
from app.ingest.sources.fixtures import FixtureSource
from app.ingest.sources.pyfinews_source import PyfinewsSource
from tests.unit.test_pyfinews_source import publisher, sample_search


@pytest.fixture
def no_network(monkeypatch):
    def deny(*a, **k):
        raise OSError("сеть запрещена в тесте")
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket.socket, "connect", deny)


def live():
    return PyfinewsSource(search=sample_search, transport=httpx.MockTransport(publisher), pause_s=0)


class Broken(Source):
    name = "broken"

    def fetch_list(self, since=None):
        raise RuntimeError("источник упал")

    def fetch_article(self, link):
        raise AssertionError


class HalfBroken(Source):
    name = "half"

    def fetch_list(self, since=None):
        return [Link(url="https://x/1"), Link(url="https://x/2")]

    def fetch_article(self, link):
        if link.url.endswith("1"):
            raise TimeoutError("таймаут")
        return RawArticle(item_id="h2", url=link.url, title="Новость", text="Текст новости про ставку 14%",
                          published_at=datetime(2026, 10, 23, 13, 0, tzinfo=timezone.utc), source_name="X")


def test_live_sample_saved_without_network(no_network):
    s = fetch.run([live()])
    assert s["new"] == 2 and s["errors"] == 1  # один запрос в образце падает
    row = connect().execute("SELECT * FROM news_items WHERE text_status = 'full'").fetchone()
    assert row["url"] == "https://example.org/cbr" and row["published_at"].endswith("+00:00")
    assert "23 октября" in row["text"] and row["synthetic"] == 0 and row["topic_hint"] == "rate"


def test_rerun_does_not_duplicate(no_network):
    first, second = fetch.run([live()]), fetch.run([live()])
    assert second["new"] == 0 and second["updated"] == first["new"]
    assert connect().execute("SELECT COUNT(*) FROM news_items").fetchone()[0] == first["new"]


def test_failures_do_not_stop_others(no_network):
    s = fetch.run([Broken(), HalfBroken(), FixtureSource(include_holdout=False)])
    assert s["errors"] == 2 and s["new"] == 45  # 44 фикстуры + 1 из HalfBroken


def test_same_text_under_other_url_is_duplicate(no_network):
    fetch.run([HalfBroken()])

    class Copy(HalfBroken):
        def fetch_article(self, link):
            a = super().fetch_article(link)
            return a.model_copy(update={"item_id": "copy", "url": "https://mirror/2"})
    assert fetch.run([Copy()])["duplicates"] == 1


def test_query_hint_used_when_keywords_fail(no_network):
    fetch.run([live()])
    classify.run()
    topics = dict(connect().execute("SELECT item_id, topic FROM news_class").fetchall())
    assert set(topics.values()) <= set(classify.TOPICS) and "other" not in topics.values()


def test_remove_synthetic(no_network):
    fetch.run([FixtureSource(), live()])
    assert fetch.remove_synthetic() == 50
    assert connect().execute("SELECT COUNT(*) FROM news_items").fetchone()[0] == 2
