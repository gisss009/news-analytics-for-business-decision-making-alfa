from pydantic import SecretStr

from app.core.config import settings
from app.core.db import connect
from app.ingest import offline
from app.ingest.classify import accuracy, classify
from app.ingest.fixtures import load_fixtures


def test_topic_accuracy_on_labelled_fixtures():
    acc = accuracy(load_fixtures(include_holdout=True))
    print("classify accuracy:", acc)
    assert acc["main"] >= 0.8 and acc["holdout"] >= 0.8


def test_fields_for_key_rate_news():
    c = classify("Банк России сохранил ключевую ставку на уровне 14%",
                 "Совет директоров Банка России сохранил ключевую ставку 14,0% годовых.")
    assert c.topic == "rate" and c.method == "keywords" and "Банк России" in c.entities and "RU" in c.geo


def test_sectors_and_geo():
    c = classify("Импортёры продуктов из Китая повышают цены", "Дистрибьюторы продовольствия из Китая и Турции.")
    assert "food_trade" in c.sectors and {"CN", "TR"} <= set(c.geo)


def test_noise_is_other():
    assert classify("Сборная выиграла матч", "Футболисты обыграли соперника со счётом 2:1.").topic == "other"


def test_fallback_when_model_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "llm_mode", "real")
    monkeypatch.setattr(settings, "llm_api_key", SecretStr(""))  # модель недоступна
    c = classify("Курс доллара вырос до 92 рублей", "Рубль ослаб на фоне роста импорта.")
    assert c.method == "keywords" and c.topic == "fx"


def test_pipeline_writes_news_class():
    offline.run()
    n = connect().execute("SELECT COUNT(*) FROM news_class").fetchone()[0]
    assert n == connect().execute("SELECT COUNT(*) FROM news_items").fetchone()[0]
