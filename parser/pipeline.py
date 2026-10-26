"""Сборка карточек банка и новостей в один JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from parser.bank import Skip, load_bank_directory
from parser.news import fetch_news
from parser.schema import ALFA_RESEARCH, EXTERNAL_NEWS, MaterialCard


@dataclass
class RunResult:
    cards: list[MaterialCard] = field(default_factory=list)
    skipped: list[Skip] = field(default_factory=list)

    def write(self, out: Path) -> Path:
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = [card.to_dict() for card in self.cards]
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        topics: dict[str, int] = {}
        for card in self.cards:
            for topic in card.topics:
                topics[topic] = topics.get(topic, 0) + 1
        report = {
            "materials": len(self.cards),
            "bank": sum(card.source_type == ALFA_RESEARCH for card in self.cards),
            "news": sum(card.source_type == EXTERNAL_NEWS for card in self.cards),
            "skipped": [item.to_dict() for item in self.skipped],
            "topics": topics,
            "topic_method": "словарь и запросы pyfinews, без LLM",
        }
        report_path = out.parent / "report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report_path


def run(
    alfa_dir: Path,
    *,
    include_news: bool = True,
    hours: float = 168,
    per_topic: int = 4,
    search=None,
    retrieved_at: str | None = None,
) -> RunResult:
    cards, skipped = load_bank_directory(alfa_dir, retrieved_at=retrieved_at)
    if include_news:
        news_cards, news_skipped = fetch_news(
            hours=hours,
            per_topic=per_topic,
            search=search,
            retrieved_at=retrieved_at,
        )
        cards.extend(news_cards)
        skipped.extend(news_skipped)
    return RunResult(cards, skipped)
