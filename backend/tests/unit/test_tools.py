import pytest
from pydantic import ValidationError

from app.agents.events import get_event, list_events
from app.agents.tools import AccessDenied, RefNotFound, ToolContext, ToolNotAllowed, call_tool, resolve_ref
from app.core.db import connect

CTX = ToolContext(company_id="U_S0001", step="retriever", run_id="r_t")


def tool_calls():
    return connect().execute("SELECT actor, tool, ok FROM tool_calls WHERE tool NOT LIKE 'llm:%' ORDER BY id").fetchall()


def test_tools_work_and_are_logged(demo_db):
    prof = call_tool(CTX, "profile_get", company_id="U_S0001")
    assert prof["name"].startswith("СтройИнвест") and prof["features"] and prof["exposures"]
    hits = call_tool(CTX, "news_search", query="ключевая ставка", k=3)
    assert hits[0]["ref"].startswith("news:")
    th = call_tool(CTX, "analytics_search", query="ключевая ставка", filters={"topic": "rate"})
    assert th[0]["ref"].startswith("doc:")
    assert call_tool(CTX, "graph_query", company_id="U_S0001", kind="concentration")["suppliers_count"] > 0
    assert call_tool(CTX, "source_open", ref="news:n001#f1")["quote"].startswith("Совет директоров")
    rows = tool_calls()
    assert [r["tool"] for r in rows] == ["profile_get", "news_search", "analytics_search", "graph_query", "source_open"]
    assert all(r["ok"] == 1 and r["actor"] == "retriever" for r in rows)


def test_tool_outside_step_allowlist_rejected(demo_db):
    with pytest.raises(ToolNotAllowed):
        call_tool(ToolContext("U_S0001", "interpreter"), "news_search", query="ставка")
    with pytest.raises(ToolNotAllowed):
        call_tool(ToolContext("U_S0001", "ranker"), "source_open", ref="news:n001")
    with pytest.raises(ToolNotAllowed):
        call_tool(CTX, "send_payment", amount=1)
    assert [r["ok"] for r in tool_calls()] == [0, 0, 0]


def test_other_company_data_rejected(demo_db):
    with pytest.raises(AccessDenied):
        call_tool(CTX, "profile_get", company_id="U_S0002")
    with pytest.raises(AccessDenied):
        call_tool(CTX, "graph_query", company_id="U_S0002", kind="suppliers")
    rows = tool_calls()
    assert len(rows) == 2 and all(r["ok"] == 0 for r in rows)


def test_invalid_args_rejected(demo_db):
    with pytest.raises(ValidationError):
        call_tool(CTX, "graph_query", company_id="U_S0001", kind="delete_all")


def test_resolve_all_ref_kinds(demo_db):
    assert resolve_ref("news:n001", "U_S0001")["title"]
    assert resolve_ref("doc:key_rate_11sep2026#p1", "U_S0001")["excerpt_only"] is True
    assert "14,0%" in resolve_ref("thesis:key_rate_11sep2026#t1", "U_S0001")["quote"]
    assert resolve_ref("feat:has_loans", "U_S0001")["value"] is True
    assert resolve_ref("exp:rate_sensitivity", "U_S0001")["score"] > 0.5
    cp = call_tool(CTX, "graph_query", company_id="U_S0001", kind="suppliers")[0]["ref"]
    assert resolve_ref(cp, "U_S0001")["kind"] == "counterparty"
    for bad in ("news:zzz", "doc:key_rate_11sep2026#p99", "feat:nope", "cp:U_S0002", "garbage"):
        with pytest.raises(RefNotFound):
            resolve_ref(bad, "U_S0001")


def test_events(demo_db):
    ev = get_event("ev_n001")
    assert ev["size"] == 3 and ev["topic"] == "rate" and ev["items"][0]["facts"]
    assert len(list_events()) == 45
