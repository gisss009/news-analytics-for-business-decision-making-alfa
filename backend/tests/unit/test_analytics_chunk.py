import pytest

from app.core.db import connect
from app.ingest.analytics_chunk import evaluate, extract_theses, horizon, load_from_pdfs
from app.ingest.analytics_parse import Doc, Page, analytics_dir, parse_all

PAGE1 = ("Центр макроэкономического анализа\n\n11 сентября 2026 г.\n\n"
         "ЦБ РФ принял решение оставить ставку неизменной на уровне 14,0%: ЦБ РФ на сегодняшнем заседании принял решение "
         "взять паузу и оставить ставку неизменной на уровне 14,0%.\n\n"
         "Я Мы ожидаем сохранения паузы на заседании 23 октября: С учетом риторики ЦБ РФ мы меняем наш взгляд на динамику "
         "ключевой ставки на этот год. Если раньше мы ориентировались на ставку на уровне 13,5% на конец 2026 г., то теперь "
         "мы ожидаем ее сохранения на текущем значении 14,0% до конца года. При этом наш прогноз по ставке на конец 2027 г. "
         "остается на уровне 12,0%.\n\nИсточник: Bloomberg, Альфа-Банк")
PAGE2 = "Инфляционные ожидания населения в августе составили 13,7%, по нашим оценкам, риски для инфляции сохраняются."


def doc() -> Doc:
    return Doc(doc_id="key_rate_11sep2026", title="Ключевая ставка", date="2026-09-11", kind="macro",
               file="ALFA-Macro_Insights-Policy_Rate_11Sep.pdf", pages=[Page(n=1, text=PAGE1), Page(n=2, text=PAGE2)])


def test_theses_are_verbatim_and_typed():
    ts = extract_theses(doc())
    assert len(ts) >= 3
    pages = {1: PAGE1, 2: PAGE2}
    for t in ts:
        assert t.quote in pages[t.page] and t.thesis_id.startswith("key_rate_11sep2026#t") and t.topic != "other"
    assert any("14,0% до конца года" in t.quote and t.topic == "rate" and t.horizon == "2026" for t in ts)
    assert not any(t.quote.startswith("Я ") for t in ts)  # артефакт маркера списка срезан
    assert not any("Bloomberg" in t.quote for t in ts)


def test_horizon():
    assert horizon("рост в 4К26 замедлится", "2026") == "2026-Q4"
    assert horizon("до конца года", "2026") == "2026" and horizon("без срока", "2026") is None


def test_load_from_pdfs_writes_full_pages():
    s = load_from_pdfs([doc()])
    conn = connect()
    assert s["theses"] >= 3 and s["analytics_source"] == "pdf"
    page = conn.execute("SELECT text, excerpt_only FROM analytics_pages WHERE doc_id = 'key_rate_11sep2026' AND page = 1").fetchone()
    assert page["excerpt_only"] == 0 and page["text"] == PAGE1
    rows = conn.execute("SELECT t.quote, p.text FROM theses t JOIN analytics_pages p USING (doc_id, page)").fetchall()
    assert all(r["quote"] in r["text"] for r in rows)


def test_evaluate_against_manual_quotes():
    e = evaluate([doc()])
    assert e["gold_quotes"] == 6  # ручных цитат у этого документа
    assert e["ocr_coverage"] >= 0.5 and e["thesis_recall"] >= 0.3


@pytest.mark.skipif(not (analytics_dir() / ".ocr").exists(), reason="нет кэша OCR (python scripts/ocr.py)")
def test_real_ocr_documents_have_three_theses_each():
    docs, skipped = parse_all()
    assert len(docs) == 9 and not skipped
    for d in docs:
        ts = extract_theses(d)
        pages = {p.n: p.text for p in d.pages}
        assert len(ts) >= 3, d.doc_id
        assert all(t.quote in pages[t.page] for t in ts)
    assert evaluate(docs)["ocr_coverage"] >= 0.9
