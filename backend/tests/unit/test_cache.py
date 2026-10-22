from app.agents import interpreter
from app.agents.cache import get_or_run
from app.core.db import session


def llm_calls() -> int:
    with session() as conn:
        return conn.execute("SELECT COUNT(*) FROM tool_calls WHERE tool LIKE 'llm:%'").fetchone()[0]


def test_second_request_does_not_call_llm(demo_db):
    first, cached1 = get_or_run("U_S0001", "ev_n001")
    n = llm_calls()
    second, cached2 = get_or_run("U_S0001", "ev_n001")
    assert not cached1 and cached2 and second == first and llm_calls() == n


def test_prompt_version_change_invalidates(demo_db, monkeypatch):
    get_or_run("U_S0001", "ev_n001")
    monkeypatch.setattr(interpreter, "PROMPT_VERSION", "interp-v2")
    _, cached = get_or_run("U_S0001", "ev_n001")
    assert not cached


def test_new_material_and_profile_change_invalidate(demo_db):
    get_or_run("U_S0001", "ev_n001")
    with session() as conn:
        conn.execute("UPDATE companies SET has_leasing = 0 WHERE company_id = 'U_S0001'")
    assert not get_or_run("U_S0001", "ev_n001")[1]
    with session() as conn:
        conn.execute("INSERT INTO news_items (item_id, url, title, text, published_at, source_name, source_type, hash) "
                     "VALUES ('x1', 'u', 't', 'текст новости', '2026-09-30T00:00:00+00:00', 's', 'news', 'h')")
    assert not get_or_run("U_S0001", "ev_n001")[1]


def test_key_depends_on_company_and_role(demo_db):
    get_or_run("U_S0001", "ev_n001", "cfo")
    assert not get_or_run("U_S0001", "ev_n001", "treasurer")[1]
    assert not get_or_run("U_S0004", "ev_n001", "cfo")[1]
