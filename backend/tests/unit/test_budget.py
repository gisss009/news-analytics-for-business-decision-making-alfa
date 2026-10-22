import json

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.core.db import connect
from app.llm import budget, client
from app.llm.client import BudgetExceeded, LLMError, complete


@pytest.fixture
def real_llm(monkeypatch):
    monkeypatch.setattr(settings, "llm_mode", "real")
    monkeypatch.setattr(settings, "llm_api_key", SecretStr("test-key"))
    calls = []

    def handler(req):
        calls.append(json.loads(req.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ответ"}}],
                                         "usage": {"prompt_tokens": 600, "completion_tokens": 400}})
    monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
    return calls


def test_identical_request_served_from_cache(real_llm):
    msgs = [{"role": "user", "content": "вопрос"}]
    assert complete("interpret", msgs) == "ответ"
    assert complete("interpret", msgs) == "ответ"
    assert len(real_llm) == 1
    rows = connect().execute("SELECT tokens FROM tool_calls ORDER BY id").fetchall()
    assert [r["tokens"] for r in rows] == [1000, 0]


def test_usage_recorded_in_rub(real_llm):
    complete("interpret", [{"role": "user", "content": "x"}])
    row = connect().execute("SELECT calls, tokens, rub FROM llm_usage WHERE mode = 'real'").fetchone()
    assert row["calls"] == 1 and row["tokens"] == 1000
    assert row["rub"] == pytest.approx(budget.cost_rub("glm-5.3-flash", 1000))


def test_call_blocked_after_limit(real_llm, monkeypatch):
    monkeypatch.setattr(settings, "daily_budget_rub", 0.06)
    complete("interpret", [{"role": "user", "content": "первый"}])  # 0.05 руб.
    with pytest.raises(BudgetExceeded, match="бюджет"):
        complete("interpret", [{"role": "user", "content": "второй " * 400}])
    assert len(real_llm) == 1
    assert issubclass(BudgetExceeded, LLMError)
    last = connect().execute("SELECT ok FROM tool_calls ORDER BY id DESC").fetchone()
    assert last["ok"] == 0


def test_cached_answer_available_even_over_limit(real_llm, monkeypatch):
    msgs = [{"role": "user", "content": "повтор"}]
    complete("interpret", msgs)
    monkeypatch.setattr(settings, "daily_budget_rub", 0.0)
    assert complete("interpret", msgs) == "ответ"


def test_warning_at_80_percent(real_llm, monkeypatch):
    monkeypatch.setattr(settings, "daily_budget_rub", 0.1)
    complete("interpret", [{"role": "user", "content": "x"}])  # 0.05 руб. = 50%
    warned = []
    monkeypatch.setattr(budget.log, "warning", lambda msg, **kw: warned.append(msg))
    budget.check_and_reserve("glm-5.3-flash", 100)  # 0.055 руб. = 55%: без предупреждения
    budget.check_and_reserve("glm-5.3-flash", 700)  # 0.085 руб. = 85%
    assert warned == ["budget_warning"]


def test_stub_mode_costs_nothing():
    budget.record("glm-5.3-flash", 1000, "stub")
    assert budget.spent_today() == 0
    assert budget.status()["limit_rub"] == 500
