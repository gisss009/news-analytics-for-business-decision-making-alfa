import pytest

from app.ingest import offline
from app.ingest.index import Filters, search


@pytest.fixture(autouse=True)
def pipeline():
    offline.run()


@pytest.mark.parametrize("query,expected", [
    ("решение по ключевой ставке", {"news:n001", "news:n002", "news:n003"}),
    ("золото подорожало за август", {"news:n018", "news:n019"}),
    ("утильсбор на автомобили", {"news:n027"}),
    ("задержки платежей в Китай", {"news:n036"}),
    ("налог на добычу золота", {"news:n034"}),
])
def test_news_queries_return_expected_top(query, expected):
    hits = search(query, "news", k=3)
    assert hits and hits[0].ref in expected, [h.ref for h in hits]


def test_morphology_normalized():
    a = {h.ref for h in search("ставки", "news", k=5)}
    b = {h.ref for h in search("ставкой", "news", k=5)}
    assert a == b and a


def test_analytics_returns_doc_page_refs():
    hits = search("ключевая ставка 14,0% до конца года", "analytics", k=3)
    assert hits[0].ref == "doc:key_rate_11sep2026#p1"
    assert hits[0].extra["thesis_id"].startswith("key_rate_11sep2026#t") and hits[0].snippet


def test_filters():
    assert all(h.topic == "commodities" for h in search("цены рост", "news", Filters(topic="commodities"), k=10))
    gold = search("цены", "news", Filters(sector="gold_mining"), k=10)
    assert gold and all("gold_mining" in h.sectors for h in gold)
    late = search("ставка", "news", Filters(date_from="2026-09-15"), k=10)
    assert late and all(h.date >= "2026-09-15" for h in late)
    early = search("ставка", "news", Filters(date_to="2026-09-11"), k=10)
    assert early and all(h.date[:10] <= "2026-09-11" for h in early)
    blogs = search("курс рубля", "news", Filters(source_type="blog"), k=10)
    assert [h.ref for h in blogs] == ["news:n043"]
    assert not any(h.extra.get("holdout") for h in search("золото", "news", Filters(include_holdout=False), k=20))


def test_stale_analytics_hidden_by_default():
    assert not any("russian_steels" in h.ref for h in search("цены на сталь", "analytics", k=10))
    assert any("russian_steels" in h.ref for h in search("цены на сталь", "analytics", Filters(include_stale=True), k=10))


def test_empty_and_garbage_queries():
    assert search("", "news") == [] and search("и в на", "news") == []
    assert search('"OR AND NOT (', "news") == []
