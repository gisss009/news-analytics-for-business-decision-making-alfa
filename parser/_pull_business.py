"""Выгрузка деловой ленты: python -m parser._pull_business"""

import json
from pathlib import Path

from parser.news import fetch_business_news


def main() -> None:
    cards, skipped = fetch_business_news(hours=72, per_query=5)
    out = Path("data/out/business_news.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps([card.to_dict() for card in cards], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"новостей {len(cards)}, пропусков {len(skipped)}")
    for skip in skipped:
        print("пропуск", skip.target, skip.reason)


if __name__ == "__main__":
    main()
