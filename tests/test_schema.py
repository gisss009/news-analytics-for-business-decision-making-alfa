import json
import unittest
from datetime import datetime, timezone

from parser.schema import (
    ALFA_RESEARCH,
    EXTERNAL_NEWS,
    MaterialCard,
    SourceAnchor,
    Statement,
    card_from_bank,
    card_from_pyfinews,
    card_id,
)


class SchemaTests(unittest.TestCase):
    def test_news_and_bank_share_the_same_fields(self) -> None:
        news = card_from_pyfinews(
            {
                "title": "ЦБ сохранил ставку",
                "url": "https://example.com/rate",
                "source": "Интерфакс",
                "published_at": "2026-09-11T10:00:00+00:00",
                "summary": "Ставка осталась 14%.",
            },
            retrieved_at="2026-09-11T12:00:00+00:00",
        )
        bank = card_from_bank(
            title="Ключевая ставка ЦБ РФ",
            path="data/alfa/key-rate.pdf",
            text="Риторика стала жёстче.",
            page=1,
            published_at="2026-09-11",
            retrieved_at="2026-09-11T12:00:00+00:00",
        )

        self.assertEqual(set(news.to_dict()), set(bank.to_dict()))
        self.assertEqual(news.source_type, EXTERNAL_NEWS)
        self.assertEqual(bank.source_type, ALFA_RESEARCH)
        self.assertEqual(news.bank_position, [])
        self.assertEqual(news.model_inference, [])
        self.assertEqual(bank.model_inference, [])
        self.assertEqual(news.anchor.kind, "url")
        self.assertEqual(bank.anchor.kind, "file")
        self.assertEqual(bank.anchor.page, 1)

    def test_pyfinews_prefers_resolved_url_and_full_text(self) -> None:
        published = datetime(2026, 8, 31, 6, 0, tzinfo=timezone.utc)
        card = card_from_pyfinews(
            {
                "title": "Инфляция за неделю",
                "url": "https://news.google.com/rss/articles/abc",
                "resolved_url": "https://www.rbc.ru/inflation",
                "source": "РБК",
                "published_at": published,
                "summary": "Короткий анонс",
                "text": "Полный текст заметки.",
            }
        )
        self.assertEqual(card.anchor.url, "https://www.rbc.ru/inflation")
        self.assertEqual(card.text, "Полный текст заметки.")
        self.assertEqual(card.published_at, "2026-08-31T06:00:00+00:00")
        self.assertEqual(card.id, card_id(EXTERNAL_NEWS, "https://www.rbc.ru/inflation"))

    def test_same_source_keeps_the_same_id(self) -> None:
        first = card_from_bank(title="Бонд бриф", path="data/alfa/bond.pdf")
        second = card_from_bank(title="Бонд бриф, другая вычитка", path="data/alfa/bond.pdf")
        self.assertEqual(first.id, second.id)

    def test_external_news_cannot_carry_bank_position(self) -> None:
        with self.assertRaises(ValueError):
            MaterialCard(
                id="x",
                source_type=EXTERNAL_NEWS,
                title="Новость",
                text="",
                published_at=None,
                retrieved_at="2026-09-11T12:00:00+00:00",
                source_name="",
                anchor=SourceAnchor(kind="url", url="https://example.com/a"),
                bank_position=[Statement("Позиция банка")],
            )

    def test_json_roundtrip_keeps_cyrillic(self) -> None:
        card = card_from_bank(title="Обзор рынка золота", path="data/alfa/gold.pdf")
        payload = json.loads(card.to_json())
        self.assertEqual(payload["title"], "Обзор рынка золота")
        self.assertEqual(payload["anchor"]["path"], "data/alfa/gold.pdf")
        self.assertNotIn("model", payload)


if __name__ == "__main__":
    unittest.main()
