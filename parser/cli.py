"""Команда сборки материалов."""

from __future__ import annotations

import argparse
from pathlib import Path

from parser.pipeline import run


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    result = run(
        Path(arguments.alfa),
        include_news=not arguments.no_news,
        hours=arguments.hours,
        per_topic=arguments.per_topic,
    )
    out = Path(arguments.out)
    report_path = result.write(out)
    counts: dict[str, int] = {}
    for card in result.cards:
        for topic in card.topics:
            counts[topic] = counts.get(topic, 0) + 1
    topics = ", ".join(f"{name} {count}" for name, count in sorted(counts.items())) or "нет"
    print(f"Материалы: {len(result.cards)}")
    print(f"Банк: {sum(card.source_type == 'alfa_research' for card in result.cards)}")
    print(f"Новости: {sum(card.source_type == 'external_news' for card in result.cards)}")
    print(f"Пропущено: {len(result.skipped)}")
    print(f"Темы: {topics}")
    print(f"Карточки: {out}")
    print(f"Отчёт: {report_path}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Собрать карточки аналитики Альфа-Банка и деловых новостей pyfinews"
    )
    parser.add_argument("--alfa", default="data/alfa", help="папка с PDF банка")
    parser.add_argument("--out", default="data/out/materials.json", help="куда писать карточки")
    parser.add_argument("--hours", type=float, default=168, help="глубина новостей в часах")
    parser.add_argument("--per-topic", type=int, default=4, help="сколько новостей брать на тему")
    parser.add_argument("--no-news", action="store_true", help="только PDF банка, без pyfinews")
    return parser
