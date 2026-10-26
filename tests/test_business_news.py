import unittest
from datetime import datetime, timezone

from pyfinews.models import NewsArticle

from parser.news import fetch_business_news

WHEN = datetime(2026, 10, 22, 15, 0, tzinfo=timezone.utc)


class BusinessNewsTests(unittest.TestCase):
    def test_keeps_business_and_drops_noise(self) -> None:
        def search(query: str, *, hours: float, max_articles: int):
            if "экономик" in query:
                return [
                    NewsArticle(
                        title="Экономика России замедлила рост в третьем квартале - РБК",
                        url="https://example.com/econ",
                        source="РБК",
                        published_at=WHEN,
                        retrieved_at=WHEN,
                        summary="Рост ВВП оказался ниже прогноза.",
                    ),
                    NewsArticle(
                        title="Число заявок на пособие по безработице в США упало - Финансы Mail",
                        url="https://example.com/us",
                        source="Финансы Mail",
                        published_at=WHEN,
                        retrieved_at=WHEN,
                        summary="Заявки в США.",
                    ),
                ]
            return []

        cards, skipped = fetch_business_news(search=search, hours=72, per_query=5)
        self.assertEqual(skipped, [])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].source_name, "РБК")
        self.assertIn("Экономика", cards[0].topics)
