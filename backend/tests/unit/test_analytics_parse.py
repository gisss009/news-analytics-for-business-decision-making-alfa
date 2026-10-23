import hashlib
import json

import pytest

from app.ingest.analytics_parse import OcrMissing, meta_for, normalize, parse_all, parse_pdf


def write_pdf_with_cache(d, name, pages, stale_sha=False):
    pdf = d / name
    pdf.write_bytes(b"%PDF-1.4 fake")
    sha = "0" * 64 if stale_sha else hashlib.sha256(pdf.read_bytes()).hexdigest()
    (d / ".ocr").mkdir(exist_ok=True)
    (d / ".ocr" / f"{name}.json").write_text(json.dumps(
        {"file": name, "sha256": sha, "pages": [{"page": i + 1, "text": t} for i, t in enumerate(pages)]},
        ensure_ascii=False), encoding="utf-8")
    return pdf


def test_normalize_joins_lines_and_drops_disclaimer():
    raw = ("мы ожидаем ее сохра-\nнения на уровне 14,0%\nдо конца года.\n\n"
           "Альфа-Банк, 2026 г. Все права защищены. Генеральная лицензия ЦБ РФ № 1326\n\nВторой абзац")
    assert normalize(raw) == "мы ожидаем ее сохранения на уровне 14,0% до конца года.\n\nВторой абзац"


def test_parse_pdf_uses_known_metadata(tmp_path):
    pdf = write_pdf_with_cache(tmp_path, "ALFA-Macro_Insights-Policy_Rate_11Sep.pdf", ["Ставка 14,0%\nбез изменения", ""])
    doc = parse_pdf(pdf)
    assert doc.doc_id == "key_rate_11sep2026" and doc.date == "2026-09-11"
    assert doc.pages[0].text == "Ставка 14,0% без изменения" and doc.pages[1].needs_ocr


def test_missing_or_stale_cache(tmp_path):
    (tmp_path / "new.pdf").write_bytes(b"x")
    with pytest.raises(OcrMissing):
        parse_pdf(tmp_path / "new.pdf")
    stale = write_pdf_with_cache(tmp_path, "Doc_14092026.pdf", ["текст"], stale_sha=True)
    with pytest.raises(OcrMissing, match="изменился"):
        parse_pdf(stale)
    docs, skipped = parse_all(tmp_path)
    assert docs == [] and len(skipped) == 2


def test_unknown_file_metadata(tmp_path):
    m = meta_for(tmp_path / "Bond_Brief_14092026.pdf")
    assert m["doc_id"] == "bond_brief_14092026" and m["date"] == "2026-09-14" and m["kind"] == "other"
