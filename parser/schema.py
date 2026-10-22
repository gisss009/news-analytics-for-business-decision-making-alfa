"""Общая карточка материала для новости pyfinews и обзора Альфа-Банка."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import unescape
from typing import Any, Mapping

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")

EXTERNAL_NEWS = "external_news"
ALFA_RESEARCH = "alfa_research"
SOURCE_TYPES = frozenset({EXTERNAL_NEWS, ALFA_RESEARCH})


@dataclass
class SourceAnchor:
    kind: str
    url: str | None = None
    path: str | None = None
    page: int | None = None
    quote: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"url", "file"}:
            raise ValueError("kind якоря должен быть url или file")
        if self.page is not None and self.page < 1:
            raise ValueError("номер страницы начинается с 1")


@dataclass
class Statement:
    text: str
    anchor: SourceAnchor | None = None

    def __post_init__(self) -> None:
        self.text = self.text.strip()
        if not self.text:
            raise ValueError("формулировка не может быть пустой")


@dataclass
class MaterialCard:
    id: str
    source_type: str
    title: str
    text: str
    published_at: str | None
    retrieved_at: str
    source_name: str
    anchor: SourceAnchor
    topics: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    facts: list[Statement] = field(default_factory=list)
    risks: list[Statement] = field(default_factory=list)
    opportunities: list[Statement] = field(default_factory=list)
    bank_position: list[Statement] = field(default_factory=list)
    model_inference: list[Statement] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.source_type not in SOURCE_TYPES:
            raise ValueError(f"неизвестный source_type: {self.source_type}")
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("у материала нет заголовка")
        self.text = self.text.strip()
        if self.source_type == EXTERNAL_NEWS and self.bank_position:
            raise ValueError("у внешней новости не бывает позиции банка")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def card_id(source_type: str, stable_key: str) -> str:
    payload = f"{source_type}\n{stable_key.strip()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def card_from_pyfinews(article: Mapping[str, Any], retrieved_at: str | None = None) -> MaterialCard:
    """Приводит запись pyfinews к карточке. Сеть здесь не вызывается."""

    title = _plain(article.get("title"))
    url = str(article.get("resolved_url") or article.get("url") or "").strip()
    if not url:
        raise ValueError("у новости pyfinews нет url")
    published = article.get("published_at")
    text = _plain(article.get("text") or article.get("summary"))
    return MaterialCard(
        id=card_id(EXTERNAL_NEWS, url),
        source_type=EXTERNAL_NEWS,
        title=title,
        text=text,
        published_at=_as_iso(published),
        retrieved_at=retrieved_at or _as_iso(article.get("retrieved_at")) or utc_now(),
        source_name=str(article.get("source") or "").strip(),
        anchor=SourceAnchor(kind="url", url=url),
    )


def card_from_bank(
    *,
    title: str,
    path: str,
    text: str = "",
    page: int | None = None,
    published_at: str | None = None,
    retrieved_at: str | None = None,
    source_name: str = "Альфа-Банк, центр макроэкономических исследований",
) -> MaterialCard:
    """Карточка аналитического материала банка. Текст дочитывается следующим шагом."""

    clean_path = path.strip()
    if not clean_path:
        raise ValueError("у материала банка нет пути к файлу")
    return MaterialCard(
        id=card_id(ALFA_RESEARCH, clean_path),
        source_type=ALFA_RESEARCH,
        title=title,
        text=text,
        published_at=published_at,
        retrieved_at=retrieved_at or utc_now(),
        source_name=source_name,
        anchor=SourceAnchor(kind="file", path=clean_path, page=page),
    )


def _plain(value: Any) -> str:
    if value is None:
        return ""
    text = _TAG.sub(" ", str(value))
    return _SPACE.sub(" ", unescape(text)).strip()


def _as_iso(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    return str(value)
