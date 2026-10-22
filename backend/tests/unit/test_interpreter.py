import pytest
from pydantic import SecretStr

from app.agents.bank_view import bank_view
from app.agents.events import get_event, list_events
from app.agents.interpreter import build_context, interpret
from app.agents.ranker import company_context, score_event
from app.agents.schemas import Blocks
from app.agents.tools import resolve_ref
from app.core.config import settings
from app.llm import stubs


def run(company_id, event_id):
    ev, cc = get_event(event_id), company_context(company_id)
    rel = score_event(cc, ev)
    block, used = bank_view(ev, company_id)
    return interpret(build_context(ev, cc, rel, used, "cfo"), block)


def test_reference_example_rate_and_loans(demo_db):
    blocks, method = run("U_S0001", "ev_n001")
    assert method == "stub"
    Blocks.model_validate(blocks.model_dump())  # структура валидна по схеме
    refs = blocks.basis.refs
    assert "feat:has_loans" in refs and any(r.startswith("news:n00") for r in refs)
    assert any("14,0%" in c.text and c.label == "fact" for c in blocks.what_happened.claims)
    assert blocks.bank_view.claims and not blocks.bank_view.absent
    feats = {r for c in blocks.why_it_matters.claims for r in c.refs if r.startswith(("feat:", "exp:"))}
    assert len(feats) >= 2  # связь минимум с двумя признаками компании


def test_every_claim_labelled_and_refs_resolve_for_all_events(demo_db):
    for ev in list_events():
        for company in ("U_S0001", "U_S0002", "U_S0004"):
            blocks, _ = run(company, ev["event_id"])
            for block, c in blocks.all_claims():
                assert c.label in ("fact", "bank_analytics", "model_inference") and c.refs
                for r in c.refs:
                    resolve_ref(r, company)
            assert blocks.what_happened.claims and blocks.why_it_matters.claims and blocks.actions.claims
            assert blocks.consequences.risks or blocks.consequences.opportunities


def test_gold_miner_sees_opportunity_in_gold_rally(demo_db):
    blocks, _ = run("U_S0002", "ev_n018")
    assert any("Благоприятная" in c.text for c in blocks.consequences.opportunities)


def test_speculation_is_marked(demo_db):
    blocks, _ = run("U_S0001", "ev_n043")
    assert any(c.text.startswith("Непроверенное") and c.confidence <= 0.3 for c in blocks.what_happened.claims)


def test_llm_cannot_inject_bank_claims_or_bad_labels(demo_db, monkeypatch):
    def bad(messages, data):  # модель выдаёт «факт» со ссылкой только на признак
        return {"what_happened": [{"id": "w1", "text": "x y z", "label": "fact", "refs": ["feat:sector"]}]}
    monkeypatch.setitem(stubs._HANDLERS, "interpret", bad)
    blocks, method = run("U_S0001", "ev_n001")
    assert method == "fallback" and all(c.label != "fact" or c.refs[0].startswith("news:")
                                        for c in blocks.what_happened.claims)


def test_fallback_when_model_unavailable(demo_db, monkeypatch):
    monkeypatch.setattr(settings, "llm_mode", "real")
    monkeypatch.setattr(settings, "llm_api_key", SecretStr(""))
    blocks, method = run("U_S0001", "ev_n001")
    assert method == "fallback" and blocks.why_it_matters.claims


@pytest.mark.parametrize("issue_claim", ["w1", "y1"])
def test_issues_remove_flagged_claims(demo_db, issue_claim):
    ev, cc = get_event("ev_n001"), company_context("U_S0001")
    ctx = build_context(ev, cc, score_event(cc, ev), [], "cfo")
    ctx["issues"] = [{"claim_id": issue_claim, "type": "number_mismatch", "detail": "x"}]
    blocks, _ = interpret(ctx, bank_view(ev, "U_S0001")[0])
    assert issue_claim not in {c.id for _, c in blocks.all_claims()}
