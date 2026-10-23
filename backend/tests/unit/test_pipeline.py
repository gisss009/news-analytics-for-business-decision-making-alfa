import pytest

from app.core.db import connect
from app.ingest import pipeline
from app.ingest.analytics_parse import Doc, Page
from tests.unit.test_analytics_chunk import doc
from tests.unit.test_fetch import live, no_network  # noqa: F401  (фикстура)


def state() -> dict:
    conn = connect()
    return {t: conn.execute(f"SELECT * FROM {t} ORDER BY 1, 2").fetchall()
            for t in ("news_items", "theses", "analytics_pages", "analytics_docs")}


@pytest.fixture
def no_pdfs(monkeypatch):
    monkeypatch.setattr(pipeline, "parse_all", lambda: ([], []))


def test_offline_twice_same_state_without_network(no_network, no_pdfs):  # noqa: F811
    s1 = pipeline.run()
    first = [[tuple(r) for r in rows] for rows in state().values()]
    s2 = pipeline.run()
    assert s1 == s2 and first == [[tuple(r) for r in rows] for rows in state().values()]
    assert s1["news_source"] == "fixtures" and s1["news"] >= 44


def test_auto_without_pdf_uses_manual_theses(no_pdfs):
    s = pipeline.run(analytics="auto")
    assert s["analytics_source"] == "fixtures" and s["analytics_docs"] == 9 and s["theses"] == 40
    assert connect().execute("SELECT MIN(excerpt_only) FROM analytics_pages").fetchone()[0] == 1


def test_auto_with_ocr_uses_only_ocr_theses(monkeypatch):
    monkeypatch.setattr(pipeline, "parse_all", lambda: ([doc()], []))
    s = pipeline.run(analytics="auto")
    conn = connect()
    assert s["analytics_source"] == "pdf" and s["analytics_docs"] == 1
    assert conn.execute("SELECT COUNT(*) FROM theses").fetchone()[0] == s["theses"] >= 3
    assert conn.execute("SELECT COUNT(*) FROM theses WHERE doc_id != 'key_rate_11sep2026'").fetchone()[0] == 0
    assert conn.execute("SELECT MAX(excerpt_only) FROM analytics_pages").fetchone()[0] == 0


def test_auto_with_missing_ocr_cache_falls_back(monkeypatch):
    monkeypatch.setattr(pipeline, "parse_all", lambda: ([doc()], ["b.pdf: нет кэша OCR"]))
    s = pipeline.load_analytics("auto")
    assert s["analytics_source"] == "fixtures" and s["analytics_skipped"] == 1


def test_pdf_mode_requires_ocr(no_pdfs):
    with pytest.raises(pipeline.PipelineError):
        pipeline.load_analytics("pdf")
    assert pipeline.main(["--analytics", "pdf"]) == 2


def test_fixtures_mode_ignores_pdfs(monkeypatch):
    monkeypatch.setattr(pipeline, "parse_all", lambda: ([Doc(doc_id="x", title="x", date="2026-01-01", kind="macro",
                                                             file="x.pdf", pages=[Page(n=1, text="x")])], []))
    assert pipeline.load_analytics("fixtures")["analytics_source"] == "fixtures"


def test_live_replaces_synthetic_news(no_network, no_pdfs, monkeypatch):  # noqa: F811
    pipeline.run()
    monkeypatch.setattr(pipeline, "live_source", live)
    s = pipeline.run(news="live")
    conn = connect()
    assert s["news_source"] == "live" and s["news_synthetic_removed"] >= 44
    assert conn.execute("SELECT COUNT(*) FROM news_items WHERE synthetic = 1").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM news_items").fetchone()[0] == 2


def test_live_without_network_keeps_fixtures(no_network, no_pdfs, monkeypatch):  # noqa: F811
    class Empty(pipeline.FixtureSource):
        name = "empty"

        def fetch_list(self):
            raise OSError("нет сети")
    monkeypatch.setattr(pipeline, "live_source", Empty)
    s = pipeline.run(news="live")
    assert s["news_source"] == "fixtures" and s["news"] >= 44 and s["news_errors"] == 1


def test_summary_mentions_sources(no_pdfs):
    text = pipeline.summary(pipeline.run())
    assert "аналитика: fixtures" in text and "новости: fixtures" in text
