from app.agents.events import get_event
from app.agents.planner import execute_plan, make_plan
from app.agents.state import RunState, load, save
from app.llm import stubs


def test_valid_plan_accepted_and_stored(demo_db):
    s = RunState(company_id="U_S0001", event_id="ev_n001")
    plan = make_plan(s, get_event("ev_n001"), {"name": "x"})
    assert plan.source == "llm" and plan.steps[0].tool == "profile_get"
    assert any(st.tool == "analytics_search" and st.args["filters"]["topic"] == "rate" for st in plan.steps)
    save(s)
    assert load(s.run_id).plan == plan and s.status == "PLANNED"


def test_invalid_plan_falls_back_to_default(demo_db, monkeypatch):
    monkeypatch.setitem(stubs._HANDLERS, "plan", lambda m, d: {"steps": [{"tool": "delete_db", "args": {}}]})
    s = RunState(company_id="U_S0001")
    plan = make_plan(s, get_event("ev_n001"), {})
    assert plan.source == "default" and s.trace[-1].status == "fallback"


def test_plan_for_other_company_rejected(demo_db, monkeypatch):
    monkeypatch.setitem(stubs._HANDLERS, "plan",
                        lambda m, d: {"steps": [{"tool": "profile_get", "args": {"company_id": "U_S0002"}}]})
    assert make_plan(RunState(company_id="U_S0001"), get_event("ev_n001"), {}).source == "default"


def test_broken_json_falls_back(demo_db, monkeypatch):
    monkeypatch.setitem(stubs._HANDLERS, "plan", lambda m, d: "не JSON")
    assert make_plan(RunState(company_id="U_S0001"), get_event("ev_n001"), {}).source == "default"


def test_execute_plan_collects_results(demo_db):
    s = RunState(company_id="U_S0004")
    make_plan(s, get_event("ev_n008"), {})
    results = execute_plan(s)
    assert all(r.ok for r in results) and s.status == "RETRIEVED"
    assert {r.tool for r in results} >= {"profile_get", "news_search", "analytics_search", "graph_query"}
