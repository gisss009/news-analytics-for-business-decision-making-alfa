"""Карточка аналитического PDF Альфа-Банка.

Позиция банка, риски и возможности берутся из заголовков разделов.
Остальной текст остаётся в карточке целиком, а фразы с цифрами становятся фактами.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from parser.pdf_text import PageText, PdfReadError, read_pdf
from parser.schema import SourceAnchor, Statement, card_from_bank
from parser.topics import classify

_HEADING_MARKERS = (
    "вывод",
    "взгляд",
    "позици",
    "оценка",
    "прогноз",
    "что это значит",
    "что мы думаем",
    "риск",
    "возможн",
    "ключев",
    "главное",
    "основн",
)
_BANK_MARKERS = (
    "вывод",
    "взгляд",
    "позици",
    "оценка",
    "прогноз",
    "что это значит",
    "что мы думаем",
)
_BOILERPLATE = ("центр макроэконом", "альфа-банк", "alfa-bank", "alfa bank")
_DATE_LINE = re.compile(r"^\d{1,2}\s+[а-яё]+\s+20\d{2}(?:\s+года)?$", re.IGNORECASE)
_FILE_TITLES = {
    "ALFA-7M26.pdf": "Макростатистика 7М26",
    "ALFA-consumption.pdf": "Потребление на пике",
    "ALFA-Macro_Insights-Policy_Rate_11Sep.pdf": "Ключевая ставка ЦБ РФ",
    "ALFA-macro_stat1H26.pdf": "Макростатистика 1П26",
    "ALFA_Russian_Steels_1К21PreviewUpdate_15Apr2021.pdf": "Российская сталь",
    "FI_Strategy_3Q26_22072026.pdf": "Тактический взгляд на 3-й квартал 2026",
    "Gold_digest_August26.pdf": "Обзор рынка золота, август 2026",
    "Inflation_tracker_02.pdf": "Инфляция 25–31 августа: основные выводы",
    "Бонд_Бриф_14092026.pdf": "Бонд Бриф: итоги недели",
}
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_DATE_IN_NAME = re.compile(r"(?<!\d)(\d{2})(\d{2})(20\d{2})(?!\d)")
_MAX_STATEMENTS = 4
_MAX_FACTS = 8


@dataclass(frozen=True)
class Skip:
    target: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"target": self.target, "reason": self.reason}


@dataclass
class _Section:
    heading: str | None
    body: str
    page: int


def load_bank_directory(directory: Path, retrieved_at: str | None = None):
    if not directory.exists():
        return [], [Skip(str(directory), "папка не найдена")]

    cards = []
    skipped: list[Skip] = []
    paths = sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() == ".pdf"
    )
    for path in paths:
        try:
            pages = read_pdf(path)
            cards.append(build_bank_card(path, pages, retrieved_at=retrieved_at))
        except PdfReadError as exc:
            skipped.append(Skip(_display_path(path), str(exc)))
    return cards, skipped


def build_bank_card(path: Path, pages: list[PageText], retrieved_at: str | None = None):
    usable = [page for page in pages if page.text]
    if not usable:
        raise PdfReadError("в файле нет текстового слоя")

    text = "\n\n".join(page.text for page in usable)
    title = _title(usable, path)
    sections = _sections(usable)
    anchor = SourceAnchor(kind="file", path=_display_path(path), page=usable[0].page)
    card = card_from_bank(
        title=title,
        path=anchor.path or _display_path(path),
        text=text,
        page=anchor.page,
        published_at=date_from_name(path.name),
        retrieved_at=retrieved_at,
    )
    card.bank_position = _statements(sections, "bank", anchor.path or "")
    card.risks = _statements(sections, "risks", anchor.path or "")
    card.opportunities = _statements(sections, "opportunities", anchor.path or "")
    card.facts = _facts(sections, anchor.path or "")
    card.topics, card.industries = classify(card.title, card.text)
    return card


def date_from_name(name: str) -> str | None:
    match = _DATE_IN_NAME.search(name)
    if match is None:
        return None
    day, month, year = (int(part) for part in match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _title(pages: list[PageText], path: Path) -> str:
    known = _FILE_TITLES.get(path.name)
    if known:
        return known
    for page in pages[:1]:
        for line in _lines(page.text)[:12]:
            folded = line.casefold()
            if any(piece in folded for piece in _BOILERPLATE) or _DATE_LINE.match(line):
                continue
            if 12 <= len(line) <= 140 and not line.isdigit() and not line.endswith("."):
                return line
    stem = path.stem.replace("_", " ").replace("-", " ").strip()
    return stem or path.name


def _sections(pages: list[PageText]) -> list[_Section]:
    sections: list[_Section] = []
    for page in pages:
        heading: str | None = None
        buffer: list[str] = []

        def flush() -> None:
            body = "\n".join(buffer).strip()
            if heading or body:
                sections.append(_Section(heading, body, page.page))

        for line in _lines(page.text):
            if _is_heading(line):
                flush()
                heading = line
                buffer = []
            else:
                buffer.append(line)
        flush()
    return sections


def _statements(sections: list[_Section], bucket: str, path: str) -> list[Statement]:
    found: list[Statement] = []
    for section in sections:
        if _bucket(section.heading) != bucket or not section.body:
            continue
        anchor = SourceAnchor(kind="file", path=path, page=section.page, quote=section.heading)
        for sentence in _sentences(section.body):
            if not _readable(sentence):
                continue
            found.append(Statement(sentence, anchor))
            if len(found) >= _MAX_STATEMENTS:
                return found
    return found


def _facts(sections: list[_Section], path: str) -> list[Statement]:
    found: list[Statement] = []
    for section in sections:
        if _bucket(section.heading) != "body":
            continue
        anchor = SourceAnchor(kind="file", path=path, page=section.page)
        for sentence in _sentences(section.body):
            if len(sentence) > 280 or not re.search(r"\d", sentence) or not _readable(sentence):
                continue
            found.append(Statement(sentence, anchor))
            if len(found) >= _MAX_FACTS:
                return found
    return found


def _readable(text: str) -> bool:
    letters = [char for char in text.casefold() if "а" <= char <= "я" or char == "ё"]
    return len(text) >= 20 and len(letters) >= 12


def _bucket(heading: str | None) -> str:
    if not heading:
        return "body"
    folded = heading.casefold()
    if "риск" in folded:
        return "risks"
    if "возможн" in folded:
        return "opportunities"
    if any(marker in folded for marker in _BANK_MARKERS):
        return "bank"
    return "body"


def _is_heading(line: str) -> bool:
    if not 4 <= len(line) <= 90 or line.endswith((".", ";", ",")):
        return False
    folded = line.casefold()
    if any(marker in folded for marker in _HEADING_MARKERS):
        return True
    letters = [char for char in line if char.isalpha()]
    return len(letters) >= 4 and all(char.isupper() for char in letters)


def _sentences(text: str) -> list[str]:
    parts = [_clean(part) for part in _SENTENCE.split(text)]
    return [part for part in parts if part]


def _lines(text: str) -> list[str]:
    return [_clean(line) for line in text.splitlines() if _clean(line)]


def _clean(value: str) -> str:
    return " ".join(value.split())


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()
