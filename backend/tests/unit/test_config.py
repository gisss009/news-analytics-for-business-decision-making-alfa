from app.core.config import Settings, model_routing


def test_defaults_without_env(monkeypatch):
    monkeypatch.delenv("LLM_MODE", raising=False)
    s = Settings(_env_file=None)
    assert s.llm_mode == "stub"
    assert s.daily_budget_rub == 500
    assert s.llm_api_key.get_secret_value() == ""


def test_routing_has_steps_and_prices():
    r = model_routing()
    assert r["steps"]["interpret"]
    assert r["default"] in r["prices_rub_per_1k"]
