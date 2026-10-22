from pydantic import SecretStr

from app.agents import templates
from app.agents.orchestrator import run_insight
from app.agents.state import load
from app.core.config import settings
from app.core.db import session
from app.llm import stubs


def test_full_run_passes_and_is_traced(demo_db):
    s = run_insight("U_S0001", "ev_n001")
    assert s.status == "DONE" and s.iterations == 1 and s.insight.verification.passed
    steps = [t.step for t in s.trace]
    assert steps == ["planner", "retriever", "ranker", "bank_view", "interpreter", "verifier"]
    assert "feat:has_loans" in s.insight.blocks.basis.refs and s.insight.client_features
    restored = load(s.run_id)
    assert restored.insight == s.insight and restored.status == "DONE"
    with session() as conn:
        n = conn.execute("SELECT COUNT(*) FROM tool_calls WHERE run_id = ?", (s.run_id,)).fetchone()[0]
    assert n > 5  # все вызовы инструментов и моделей привязаны к запуску


def test_injected_error_fixed_within_two_iterations(demo_db, monkeypatch):
    def flaky(messages, data):
        draft = templates.generate(data)
        if not data.get("issues"):  # первая попытка: подсаженное неверное число
            draft["what_happened"][0]["text"] = draft["what_happened"][0]["text"].replace("14,0%", "15,5%")
        return draft
    monkeypatch.setitem(stubs._HANDLERS, "interpret", flaky)
    s = run_insight("U_S0001", "ev_n001")
    assert s.status == "DONE" and s.iterations == 2
    assert not s.verifications[0].passed and s.verifications[0].issues[0].type == "number_mismatch"
    assert s.verifications[1].passed
    assert any("14,0%" in c.text for c in s.insight.blocks.what_happened.claims)


def test_iterations_are_limited_and_bad_claims_hidden(demo_db, monkeypatch):
    def always_bad(messages, data):
        draft = templates.generate(data)
        draft["what_happened"].append({"id": "w9", "text": "Ставка 99%", "label": "fact", "refs": ["news:n001#f1"]})
        return draft
    monkeypatch.setitem(stubs._HANDLERS, "interpret", always_bad)
    s = run_insight("U_S0001", "ev_n001")
    assert s.iterations == settings.max_verify_iterations and s.status == "DONE_WITH_WARNINGS"
    assert "w9" not in {c.id for _, c in s.insight.blocks.all_claims()}
    assert any("не показано" in w for w in s.insight.warnings)


def test_no_data_scenario_marked(demo_db):
    with session() as conn:
        conn.execute("DELETE FROM news_facts WHERE item_id = 'n042'")
    s = run_insight("U_S0005", "ev_n042")
    texts = [c.text for _, c in s.insight.blocks.all_claims()]
    assert any(t.startswith("Недостаточно данных") for t in texts)
    assert any("недостаточно данных" in w for w in s.insight.warnings)
    assert any("не представлена" in w for w in s.insight.warnings)


def test_fallback_when_model_unavailable(demo_db, monkeypatch):
    monkeypatch.setattr(settings, "llm_mode", "real")
    monkeypatch.setattr(settings, "llm_api_key", SecretStr(""))
    s = run_insight("U_S0002", "ev_n018")
    assert s.status == "FALLBACK" and s.insight.blocks.why_it_matters.claims
    assert s.insight.warnings[0].startswith("Модель недоступна")
    assert any(t.status == "fallback" for t in s.trace)


def test_injection_news_does_not_change_behaviour(demo_db):
    s = run_insight("U_S0001", "ev_n043")
    # текст новости попадает в ответ только как помеченная цитата источника, а не как действие для клиента
    for _, c in s.insight.blocks.all_claims():
        assert "перевести все средства" not in c.text or c.text.startswith("Непроверенное")
    assert s.insight.relevance.score < 0.3
    assert any("анонимный блог" in w for w in s.insight.warnings)
    assert all(c.text.startswith("Непроверенное") or "Игнорируй" not in c.text for c in s.insight.blocks.what_happened.claims)
