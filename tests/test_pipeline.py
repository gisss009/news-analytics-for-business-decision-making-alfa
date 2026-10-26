import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import fitz
from pyfinews.exceptions import PyfinewsError
from pyfinews.models import NewsArticle

from parser.bank import date_from_name
from parser.cli import main
from parser.pipeline import run

FONT = Path(r"C:\Windows\Fonts\arial.ttf")
WHEN = datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc)


class PipelineTests(unittest.TestCase):
    def test_unseen_bank_note_and_broken_files(self) -> None:
        with TemporaryDirectory() as raw:
            folder = Path(raw)
            good = folder / "wheat.pdf"
            _write_note(good)
            (folder / "empty.pdf").write_bytes(b"")
            (folder / "broken.pdf").write_bytes(b"this is not a pdf")

            def search(query: str, *, hours: float, max_articles: int):
                if "электроэнерг" in query:
                    raise PyfinewsError("лента недоступна")
                if "санкц" not in query:
                    return []
                return [
                    NewsArticle(
                        title="МИД прокомментировал 18-й пакет санкций",
                        url="https://example.com/sanctions-18",
                        source="Интерфакс",
                        published_at=WHEN,
                        retrieved_at=WHEN,
                        summary="18-й пакет ограничивает поставки оборудования.",
                        query=query,
                    )
                ]

            result = run(
                folder,
                include_news=True,
                hours=24,
                per_topic=1,
                search=search,
                retrieved_at="2026-10-22T12:00:00+00:00",
            )
            titles = [card.title for card in result.cards]
            self.assertIn("Пшеница подорожала на 12%", titles)
            bank = next(card for card in result.cards if card.title.startswith("Пшеница"))
            self.assertIn("Сырьё", bank.topics)
            self.assertIn("Агросектор", bank.industries)
            self.assertTrue(bank.bank_position)
            self.assertEqual(bank.bank_position[0].anchor.page, 2)
            self.assertTrue(any("12%" in fact.text for fact in bank.facts))
            self.assertEqual(bank.model_inference, [])

            news = next(card for card in result.cards if card.source_type == "external_news")
            self.assertIn("Санкции и дипломатия", news.topics)
            self.assertEqual(news.bank_position, [])
            self.assertTrue(news.facts)

            reasons = {item.reason for item in result.skipped}
            self.assertIn("файл пустой", reasons)
            self.assertIn("файл не читается как PDF", reasons)
            self.assertTrue(any(item.target.startswith("тарифы") for item in result.skipped))

            out = folder / "materials.json"
            self.assertEqual(main(["--alfa", str(folder), "--out", str(out), "--no-news"]), 0)
            saved = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(saved), 1)
            report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["bank"], 1)
            self.assertEqual(report["news"], 0)
            self.assertEqual(report["topic_method"], "словарь и запросы pyfinews, без LLM")

    def test_date_from_bond_filename(self) -> None:
        self.assertEqual(date_from_name("Бонд_Бриф_14092026.pdf"), "2026-09-14")
        self.assertIsNone(date_from_name("Inflation_tracker_02.pdf"))


def _write_note(path: Path) -> None:
    document = fitz.open()
    regular = document.new_page()
    regular.insert_font(fontname="arial", fontfile=str(FONT))
    regular.insert_text((72, 80), "Пшеница подорожала на 12%", fontname="arial", fontsize=16)
    regular.insert_text(
        (72, 110),
        "Внутренние цены выросли на 12% за неделю.",
        fontname="arial",
        fontsize=12,
    )
    view = document.new_page()
    view.insert_font(fontname="arial", fontfile=str(FONT))
    view.insert_text((72, 80), "Наш взгляд", fontname="arial", fontsize=16)
    view.insert_text(
        (72, 110),
        "Для агросектора это повышает выручку.",
        fontname="arial",
        fontsize=12,
    )
    document.save(path)
    document.close()


if __name__ == "__main__":
    unittest.main()
