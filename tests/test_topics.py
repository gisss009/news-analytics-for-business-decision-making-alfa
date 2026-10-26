import unittest

from parser.topics import classify


class TopicTests(unittest.TestCase):
    def test_rate_fx_and_sanctions_are_separate(self) -> None:
        rate, _ = classify("ЦБ сохранил ключевую ставку на уровне 14 процентов")
        fx, _ = classify("Доллар на Мосбирже поднялся до 93 рублей")
        sanctions, _ = classify("Евросоюз согласовал новый пакет санкций на поставки станков")
        self.assertIn("Ключевая ставка", rate)
        self.assertIn("Валютные курсы", fx)
        self.assertNotIn("Ключевая ставка", fx)
        self.assertIn("Санкции и дипломатия", sanctions)
        self.assertNotIn("Валютные курсы", sanctions)

    def test_exhibition_has_no_business_topic(self) -> None:
        topics, industries = classify("В Эрмитаже открылась выставка голландской живописи")
        self.assertEqual(topics, [])
        self.assertEqual(industries, [])

    def test_hint_from_the_search_query_is_kept(self) -> None:
        topics, _ = classify("Рынок ждёт решения регулятора", hinted=["Ключевая ставка"])
        self.assertEqual(topics[0], "Ключевая ставка")
