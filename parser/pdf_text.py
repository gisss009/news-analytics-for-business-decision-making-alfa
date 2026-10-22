"""Текст PDF по страницам.

Если в файле только картинки слайдов, страницы читаются через Tesseract
(rus+eng) и кэшируются рядом с PDF. Это не языковая модель.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import fitz

_TESSERACT_DIR = Path(r"C:\Program Files\Tesseract-OCR")


class PdfReadError(Exception):
    """Файл не удалось прочитать как текстовый PDF."""


@dataclass(frozen=True)
class PageText:
    page: int
    text: str


def read_pdf(path: Path) -> list[PageText]:
    if not path.exists():
        raise PdfReadError("файл не найден")
    if path.stat().st_size == 0:
        raise PdfReadError("файл пустой")
    cached = _read_cache(path)
    if cached is not None:
        return cached
    try:
        document = fitz.open(path)
    except Exception as exc:
        raise PdfReadError("файл не читается как PDF") from exc

    try:
        if document.page_count == 0:
            raise PdfReadError("в PDF нет страниц")
        pages = [
            PageText(page=index, text=(page.get_text("text") or "").strip())
            for index, page in enumerate(document, start=1)
        ]
        if not any(page.text for page in pages):
            pages = _ocr_document(document)
    finally:
        document.close()

    if not any(page.text for page in pages):
        raise PdfReadError("в файле нет текстового слоя")
    _write_cache(path, pages)
    return pages


def _ocr_document(document: fitz.Document) -> list[PageText]:
    _enable_tesseract()
    pages: list[PageText] = []
    try:
        for index, page in enumerate(document, start=1):
            textpage = page.get_textpage_ocr(language="rus+eng", dpi=110, full=True)
            text = page.get_text("text", textpage=textpage) or ""
            pages.append(PageText(page=index, text=text.strip()))
    except Exception as exc:
        raise PdfReadError("в файле нет текстового слоя, OCR не запустился") from exc
    return pages


def _enable_tesseract() -> None:
    if _TESSERACT_DIR.exists():
        os.environ["PATH"] = str(_TESSERACT_DIR) + os.pathsep + os.environ.get("PATH", "")
        os.environ.setdefault("TESSDATA_PREFIX", str(_TESSERACT_DIR / "tessdata"))


def _cache_path(path: Path) -> Path:
    return path.parent / ".ocr" / f"{path.stem}.json"


def _read_cache(path: Path) -> list[PageText] | None:
    cache = _cache_path(path)
    if not cache.exists():
        return None
    try:
        payload = json.loads(cache.read_text(encoding="utf-8"))
        stat = path.stat()
        if payload.get("size") != stat.st_size or payload.get("mtime_ns") != stat.st_mtime_ns:
            return None
        return [PageText(page=item["page"], text=item["text"]) for item in payload["pages"]]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None


def _write_cache(path: Path, pages: list[PageText]) -> None:
    if not any(page.text for page in pages):
        return
    cache = _cache_path(path)
    cache.parent.mkdir(parents=True, exist_ok=True)
    stat = path.stat()
    payload = {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "pages": [{"page": page.page, "text": page.text} for page in pages],
    }
    cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
