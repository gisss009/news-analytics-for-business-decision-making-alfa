from app.agents.bank_view import bank_view
from app.agents.events import get_event
from app.agents.interpreter import build_context, interpret
from app.agents.ranker import company_context, score_event
from app.agents.schemas import BankViewBlock, Claim, ClaimsBlock
from app.agents.verifier import verify
from app.llm import stubs


def insight(company="U_S0001", event="ev_n001"):
    ev, cc = get_event(event), company_context(company)
    block, used = bank_view(ev, company)
    blocks, _ = interpret(build_context(ev, cc, score_event(cc, ev), used, "cfo"), block)
    return blocks


def types(v):
    return {i.type for i in v.issues}


def test_correct_insight_passes(demo_db):
    for company, event in (("U_S0001", "ev_n001"), ("U_S0002", "ev_n018"), ("U_S0004", "ev_n010"), ("U_S0005", "ev_n041")):
        v = verify(insight(company, event), company)
        assert v.passed, (company, event, v.issues)


def test_wrong_number_detected(demo_db):
    b = insight()
    c = b.what_happened.claims[0]
    b.what_happened.claims[0] = c.model_copy(update={"text": c.text.replace("14,0%", "13,5%")})
    v = verify(b, "U_S0001")
    assert any(i.type == "number_mismatch" and i.claim_id == c.id and "13.5" in i.detail for i in v.issues)


def test_broken_ref_detected(demo_db):
    b = insight()
    b.what_happened.claims.append(Claim(id="w9", text="Выдуманный факт", label="fact", refs=["news:n999#f1"]))
    v = verify(b, "U_S0001")
    assert any(i.type == "bad_ref" and i.claim_id == "w9" for i in v.issues)


def test_foreign_company_feature_is_bad_ref(demo_db):
    b = insight()
    b.why_it_matters.claims.append(Claim(id="y9", text="Связь с контрагентом", label="model_inference",
                                         refs=["cp:U_S0002", "news:n001#f1"]))
    assert "bad_ref" in types(verify(b, "U_S0001"))


def test_empty_block_detected(demo_db):
    b = insight()
    b.actions = ClaimsBlock(claims=[])
    b.bank_view = BankViewBlock()
    v = verify(b, "U_S0001")
    assert {(i.type, i.block) for i in v.issues} >= {("empty_block", "actions"), ("empty_block", "bank_view")}


def test_speculation_as_fact_detected(demo_db):
    b = insight("U_S0001", "ev_n043")
    w = next(c for c in b.what_happened.claims if c.text.startswith("Непроверенное"))
    b.what_happened.claims = [w.model_copy(update={"text": w.text.replace("Непроверенное утверждение источника: ", "")})]
    assert "unsupported" in types(verify(b, "U_S0001"))


def test_contradiction_from_model(demo_db, monkeypatch):
    monkeypatch.setitem(stubs._HANDLERS, "verify",
                        lambda m, d: {"contradictions": [{"claim_ids": ["w1", "b1"], "detail": "расходятся прогнозы"}]})
    assert "contradiction" in types(verify(insight(), "U_S0001"))
