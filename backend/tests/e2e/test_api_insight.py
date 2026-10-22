"""Сквозной сценарий через HTTP: клиент → лента → событие → инсайт (без ключа LLM, режим stub)."""
import json

from fastapi.testclient import TestClient

from app.agents.schemas import Insight
from app.api.main import app
from app.core.db import session

client = TestClient(app)


def llm_calls():
    with session() as conn:
        return conn.execute("SELECT COUNT(*) FROM tool_calls WHERE tool LIKE 'llm:%'").fetchone()[0]


def test_end_to_end_insight_and_cache(demo_db):
    feed = client.get("/clients/U_S0001/feed", params={"limit": 3}).json()
    event_id = feed["events"][0]["event_id"]
    r = client.get(f"/events/{event_id}/insight", params={"client": "U_S0001"})
    assert r.status_code == 200
    body = r.json()
    ins = Insight.model_validate(body["insight"])  # валидный Insight
    assert not body["cached"] and body["label_titles"]["bank_analytics"] == "Аналитика Альфа-Банка"
    assert ins.blocks.what_happened.claims and ins.blocks.why_it_matters.claims
    for _, c in ins.blocks.all_claims():
        assert c.label and c.refs
    n = llm_calls()
    again = client.get(f"/events/{event_id}/insight", params={"client": "U_S0001"}).json()
    assert again["cached"] and llm_calls() == n


def test_stream_reports_steps_then_done(demo_db):
    with client.stream("GET", "/events/ev_n018/insight/stream", params={"client": "U_S0002"}) as r:
        text = "".join(r.iter_text())
    events = [blk.split("\n") for blk in text.strip().split("\n\n")]
    kinds = [e[0].removeprefix("event: ") for e in events]
    assert kinds[-1] == "done" and kinds.count("step") >= 6
    steps = [json.loads(e[1].removeprefix("data: "))["step"] for e in events if e[0] == "event: step"]
    assert steps[:3] == ["planner", "retriever", "ranker"] and "verifier" in steps
    done = json.loads(events[-1][1].removeprefix("data: "))
    assert done["insight"]["event"]["id"] == "ev_n018"


def test_open_refs(demo_db):
    r = client.get("/refs", params={"ref": "news:n001#f1", "client": "U_S0001"})
    assert r.status_code == 200 and "14,0%" in r.json()["quote"] and r.json()["url"]
    doc = client.get("/refs", params={"ref": "doc:key_rate_11sep2026#p1", "client": "U_S0001"}).json()
    assert doc["page"] == 1 and doc["excerpt_only"] is True
    assert client.get("/refs", params={"ref": "feat:has_loans", "client": "U_S0001"}).json()["kind"] == "feature"
    bad = client.get("/refs", params={"ref": "news:zzz", "client": "U_S0001"})
    assert bad.status_code == 404 and bad.json()["error"]["code"] == "ref_not_found"


def test_errors(demo_db):
    assert client.get("/events/ev_nope/insight", params={"client": "U_S0001"}).status_code == 404
    assert client.get("/events/ev_n001/insight").status_code == 422
