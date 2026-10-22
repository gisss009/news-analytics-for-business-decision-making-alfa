from app.agents.events import get_event
from app.agents.ranker import company_context, rank_events, score_event
from app.agents.tools import resolve_ref
from app.core.db import connect


def scores(company_id, *event_ids, role="cfo"):
    cc = company_context(company_id)
    return [score_event(cc, get_event(e), role) for e in event_ids]


def test_loans_company_prefers_rate_over_gold(demo_db):
    rate, gold = scores("U_S0001", "ev_n001", "ev_n018")
    assert rate.score > gold.score + 0.2


def test_gold_miner_prefers_gold_over_rate(demo_db):
    rate, gold = scores("U_S0002", "ev_n001", "ev_n018")
    assert gold.score > rate.score + 0.2


def test_reasons_reference_real_features(demo_db):
    for company, event in (("U_S0001", "ev_n001"), ("U_S0002", "ev_n018"), ("U_S0004", "ev_n010")):
        rel = scores(company, event)[0]
        assert rel.reasons and rel.matched_features
        for ref in rel.matched_features:
            resolve_ref(ref, company)  # бросит исключение, если признака нет


def test_unreliable_blog_ranks_low(demo_db):
    for company in ("U_S0001", "U_S0002", "U_S0004"):
        rel = scores(company, "ev_n043")[0]
        assert rel.score < 0.3 and any("блог" in r for r in rel.reasons)


def test_feeds_differ_between_companies(demo_db):
    a = [e["event_id"] for e in rank_events("U_S0001", limit=5)]
    b = [e["event_id"] for e in rank_events("U_S0002", limit=5)]
    assert a != b and not set(a[:3]) & set(b[:3])


def test_role_changes_emphasis(demo_db):
    cfo, acc = scores("U_S0002", "ev_n034", role="cfo")[0], scores("U_S0002", "ev_n034", role="accountant")[0]
    assert acc.score > cfo.score


def test_feed_item_shape_and_judge_called(demo_db):
    feed = rank_events("U_S0004", limit=3, topic="fx")
    assert all(e["topic"] == "fx" for e in feed) and feed[0]["annotation"].endswith(".")
    scores_ = [e["score"] for e in feed]
    assert scores_ == sorted(scores_, reverse=True)
    judged = connect().execute("SELECT COUNT(*) FROM tool_calls WHERE actor = 'rank_judge'").fetchone()[0]
    assert judged == 3
