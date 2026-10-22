import subprocess
import sys
from pathlib import Path

import pytest

from app.agents.schemas import Issue, Plan, PlanStep, Relevance, Verification
from app.agents.state import RunNotFound, RunState, ToolResult, load, save

BACKEND = Path(__file__).resolve().parents[2]


def sample_state() -> RunState:
    s = RunState(company_id="U_S0001", role="cfo", event_id="ev_n001")
    s.plan = Plan(steps=[PlanStep(tool="news_search", args={"query": "ставка"}, purpose="контекст")])
    s.tool_results.append(ToolResult(step="retriever", tool="news_search", args={"query": "ставка"},
                                     result=[{"ref": "news:n001"}]))
    s.relevance = Relevance(score=0.8, reasons=["есть кредиты"], matched_features=["has_loans"])
    s.verifications.append(Verification(passed=False, issues=[Issue(type="empty_block", block="actions", detail="пусто")]))
    s.iterations = 1
    s.status = "VERIFYING"
    with s.step("planner", source="default") as info:
        info["steps"] = 1
    return s


def test_save_and_load_roundtrip():
    s = sample_state()
    save(s)
    restored = load(s.run_id)
    assert restored == s
    assert restored.trace[0].step == "planner" and restored.trace[0].detail == {"source": "default", "steps": 1}


def test_restore_in_new_process(isolated_db):
    s = sample_state()
    save(s)
    code = (f"from app.core.config import settings; settings.db_path = r'{isolated_db}'; "
            f"from app.agents.state import load; s = load('{s.run_id}'); "
            f"print(s.status, s.iterations, s.relevance.matched_features[0], s.plan.steps[0].tool)")
    out = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True, check=True)
    assert out.stdout.split() == ["VERIFYING", "1", "has_loans", "news_search"]


def test_update_overwrites():
    s = sample_state()
    save(s)
    s.status = "DONE"
    save(s)
    assert load(s.run_id).status == "DONE"


def test_step_records_errors():
    s = RunState(company_id="U_S0001")
    with pytest.raises(ValueError):
        with s.step("interpreter"):
            raise ValueError("сбой")
    assert s.trace[-1].status == "error" and "сбой" in s.trace[-1].detail["error"]


def test_unknown_run():
    with pytest.raises(RunNotFound):
        load("r_missing")
