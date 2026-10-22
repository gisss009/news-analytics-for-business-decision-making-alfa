from app.core.db import connect
from app.ingest.offline import run
from app.ingest.sources.fixtures import FixtureSource


def test_idempotent_load():
    s1, s2 = run(), run()
    assert s1 == s2 and s1["news"] >= 44 and s1["analytics_docs"] == 9 and s1["theses"] >= 30
    conn = connect()
    assert conn.execute("SELECT COUNT(*) FROM news_items").fetchone()[0] == s1["news"]
    assert conn.execute("SELECT COUNT(*) FROM theses").fetchone()[0] == s1["theses"]


def test_every_quote_is_substring_of_its_page():
    run()
    rows = connect().execute(
        "SELECT t.thesis_id, t.quote, p.text FROM theses t JOIN analytics_pages p "
        "ON p.doc_id = t.doc_id AND p.page = t.page").fetchall()
    assert rows and all(r["quote"] in r["text"] for r in rows)


def test_key_rate_thesis_and_stale_doc():
    run()
    conn = connect()
    t = conn.execute("SELECT * FROM theses WHERE doc_id = 'key_rate_11sep2026' AND topic = 'rate'").fetchall()
    assert any("14,0%" in r["quote"] for r in t)
    assert conn.execute("SELECT stale FROM analytics_docs WHERE doc_id = 'russian_steels_1q21'").fetchone()[0] == 1


def test_fixture_source_interface():
    src = FixtureSource(include_holdout=False)
    links = src.fetch_list()
    art = src.fetch_article(links[0])
    assert art.synthetic and art.text and art.url.startswith("fixture://news/")
    assert not any(src.fetch_article(link).holdout for link in links)
