from app.agents.bank_view import ABSENT_NOTE, bank_view
from app.agents.events import get_event
from app.agents.tools import resolve_ref


def test_key_rate_event_finds_key_rate_document(demo_db):
    block, used = bank_view(get_event("ev_n001"), "U_S0001")
    assert not block.absent and block.claims
    assert any(c.refs[0] == "doc:key_rate_11sep2026#p1" for c in block.claims)
    assert all(c.label == "bank_analytics" for c in block.claims)
    for c in block.claims:  # каждая ссылка открывается, у тезиса есть дословная цитата
        for r in c.refs:
            resolve_ref(r, "U_S0001")
    assert all(u["quote"] for u in used)


def test_topic_without_analytics_is_explicitly_absent(demo_db):
    for ev in ("ev_n039", "ev_n036", "ev_n041"):  # IT-льготы, платежи в Китай, спорт
        block, used = bank_view(get_event(ev), "U_S0001")
        assert block.absent and not block.claims and block.note == ABSENT_NOTE and used == []


def test_commodity_must_match(demo_db):
    steel, _ = bank_view(get_event("ev_n021"), "U_S0001")  # про сталь есть только материал 2021 года
    assert steel.absent
    gold, _ = bank_view(get_event("ev_n018"), "U_S0002")
    assert gold.claims and all("gold_aug2026" in c.refs[0] for c in gold.claims)


def test_unrelated_theses_not_attached(demo_db):
    block, _ = bank_view(get_event("ev_n025"), "U_S0010")  # продажи автомобилей
    assert block.claims and all("строительств" not in c.text.lower() for c in block.claims)
