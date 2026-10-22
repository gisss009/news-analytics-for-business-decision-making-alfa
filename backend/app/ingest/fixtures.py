"""Офлайн-набор новостей (data/fixtures/news): схема, загрузка и статистика.

Все новости вымышлены (синтетика для тестов и демо), источники — «Демо-…». Цифры согласованы с материалами
аналитики банка за сентябрь 2026. Поле gold — эталонная разметка для тестов (тема, отрасли, дубль, шум).
holdout.json не используется при настройке правил и промптов.
Запуск: python -m app.ingest.fixtures
"""
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import settings
from app.data.okved import all_sectors

TOPICS = ("rate", "fx", "commodities", "inflation", "regulation", "taxes", "sanctions_trade", "industry",
          "capital_markets", "other")
Topic = Literal["rate", "fx", "commodities", "inflation", "regulation", "taxes", "sanctions_trade", "industry",
                "capital_markets", "other"]
HOLDOUT_FILE = "holdout.json"


class FixtureSource(BaseModel):
    name: str
    type: Literal["news", "blog"]


class Gold(BaseModel):
    topic: Topic
    sectors: list[str]
    geo: list[str]
    duplicate_of: str | None = None
    noise: bool = False


class NewsFixture(BaseModel):
    id: str = Field(pattern=r"^[a-z]\d{3}$")
    published_at: datetime
    source: FixtureSource
    title: str = Field(min_length=5)
    text: str = Field(min_length=40)
    gold: Gold
    holdout: bool = False


def fixtures_dir() -> Path:
    return settings.data_dir / "fixtures" / "news"


def load_fixtures(include_holdout: bool = False, path: Path | None = None) -> list[NewsFixture]:
    d = path or fixtures_dir()
    items: list[NewsFixture] = []
    for f in sorted(d.glob("*.json")):
        holdout = f.name == HOLDOUT_FILE
        if holdout and not include_holdout:
            continue
        for raw in json.loads(f.read_text(encoding="utf-8")):
            items.append(NewsFixture(**raw, holdout=holdout))
    ids = [i.id for i in items]
    if len(ids) != len(set(ids)):
        raise ValueError("повторяющиеся id в фикстурах")
    known = {i.id for i in items}
    sectors = {s.name for s in all_sectors()}
    for i in items:
        if i.gold.duplicate_of and i.gold.duplicate_of not in known:
            raise ValueError(f"{i.id}: duplicate_of ссылается на неизвестную новость")
        bad = set(i.gold.sectors) - sectors
        if bad:
            raise ValueError(f"{i.id}: неизвестные отрасли {bad}")
    return items


def stats(items: list[NewsFixture]) -> dict:
    return {
        "total": len(items),
        "holdout": sum(i.holdout for i in items),
        "topics": dict(Counter(i.gold.topic for i in items)),
        "duplicates": sum(1 for i in items if i.gold.duplicate_of),
        "duplicate_groups": len({i.gold.duplicate_of for i in items if i.gold.duplicate_of}),
        "noise": sum(i.gold.noise for i in items),
        "sources": len({i.source.name for i in items}),
    }


if __name__ == "__main__":
    for k, v in stats(load_fixtures(include_holdout=True)).items():
        print(f"{k}: {v}")
