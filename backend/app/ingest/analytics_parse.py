"""Постраничный текст PDF аналитики банка из кэша OCR (data/analytics/.ocr, создаётся scripts/ocr.py).

PDF кейса — сканы без текстового слоя, поэтому текст получается Tesseract в Docker (docker/ocr).
Здесь кэш читается, текст нормализуется (строки внутри абзаца склеиваются, переносы слов убираются,
юридический дисклеймер вырезается) и сопоставляется с метаданными документа (doc_id, название, дата, тип)
из data/analytics/fixtures/theses.json — так ссылки doc:<id>#p<page> совпадают в обоих режимах.
Запуск: python -m app.ingest.analytics_parse
"""
import hashlib
import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from app.core.config import settings

DISCLAIMER = re.compile(r"все права защищены|генеральная лицензия|несанкционированное копирование|"
                        r"является исключительной собственност|не является индивидуальной инвестицион|"
                        r"не предназначен для распространения|обратитесь к разделу «информация»", re.I)
DATE_IN_NAME = re.compile(r"(?<!\d)(\d{2})(\d{2})(20\d{2})(?!\d)")


class OcrMissing(LookupError):
    """Для PDF нет актуального кэша OCR: запустите python scripts/ocr.py."""


class Page(BaseModel):
    n: int
    text: str
    needs_ocr: bool = False
    method: str = "ocr"


class Doc(BaseModel):
    doc_id: str
    title: str
    date: str
    kind: str
    file: str
    stale: bool = False
    pages: list[Page]


def analytics_dir() -> Path:
    return settings.data_dir / "analytics"


@lru_cache
def known_docs() -> dict[str, dict]:
    """Метаданные документов по имени файла (из ручного набора тезисов)."""
    data = json.loads((analytics_dir() / "fixtures" / "theses.json").read_text(encoding="utf-8"))
    return {d["file"]: d for d in data["documents"] if d.get("file")}


def meta_for(path: Path) -> dict:
    d = known_docs().get(path.name)
    if d:
        return {k: d[k] for k in ("doc_id", "title", "date", "kind")} | {"stale": bool(d.get("stale"))}
    m = DATE_IN_NAME.search(path.name)
    when = date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat() if m else "1970-01-01"
    slug = re.sub(r"[^a-z0-9]+", "_", path.stem.lower()).strip("_") or "doc"
    return {"doc_id": slug, "title": path.stem.replace("_", " "), "date": when, "kind": "other", "stale": False}


def normalize(text: str) -> str:
    """Абзацы через пустую строку; строки внутри абзаца склеены; дисклеймер и пустые абзацы убраны."""
    text = text.replace("\r", "").replace("­", "")
    text = re.sub(r"(\w)-\n(?=[а-яёa-z])", r"\1", text)  # перенос слова по слогам
    paragraphs = []
    for block in re.split(r"\n\s*\n", text):
        p = re.sub(r"\s*\n\s*", " ", block).strip()
        p = re.sub(r"[ \t]{2,}", " ", p)
        if p and not DISCLAIMER.search(p):
            paragraphs.append(p)
    return "\n\n".join(paragraphs)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_pdf(path: Path) -> Doc:
    cache = path.parent / ".ocr" / f"{path.name}.json"
    if not cache.exists():
        raise OcrMissing(f"{path.name}: нет кэша OCR, запустите python scripts/ocr.py")
    data = json.loads(cache.read_text(encoding="utf-8"))
    if data.get("sha256") != _sha256(path):
        raise OcrMissing(f"{path.name}: PDF изменился после OCR, запустите python scripts/ocr.py")
    pages = [Page(n=p["page"], text=normalize(p["text"]), method=p.get("method", "ocr"),
                  needs_ocr=not p["text"].strip()) for p in data["pages"]]
    return Doc(file=path.name, pages=pages, **meta_for(path))


def parse_all(directory: Path | None = None) -> tuple[list[Doc], list[str]]:
    """Все PDF папки; недоступные (нет кэша OCR) попадают в список пропусков с причиной."""
    directory = directory or analytics_dir()
    docs, skipped = [], []
    for pdf in sorted(directory.glob("*.pdf")):
        try:
            docs.append(parse_pdf(pdf))
        except OcrMissing as e:
            skipped.append(str(e))
    return docs, skipped


def stats(docs: list[Doc]) -> list[dict]:
    return [{"doc_id": d.doc_id, "pages": len(d.pages), "chars": sum(len(p.text) for p in d.pages),
             "empty_pages": sum(1 for p in d.pages if len(p.text) < 50)} for d in docs]


if __name__ == "__main__":
    docs, skipped = parse_all()
    for s in stats(docs):
        print(s)
    for s in skipped:
        print("пропуск:", s)
