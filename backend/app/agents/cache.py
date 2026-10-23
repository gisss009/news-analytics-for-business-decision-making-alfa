"""Кэш инсайтов: повторный запрос того же события для той же компании и роли не запускает цикл и не тратит токены.

Ключ: компания, событие, роль, версии промптов, режим LLM, версия данных компании (профиль) и версия контента
(новости, тезисы банка). Смена любой из версий даёт новый ключ — старая запись просто перестаёт использоваться.
"""
import hashlib
import json
from datetime import datetime, timezone

from app.agents import interpreter, planner
from app.agents.orchestrator import run_insight
from app.agents.schemas import Insight
from app.core.config import settings
from app.core.db import register_schema, session

register_schema("insights_cache", """
CREATE TABLE IF NOT EXISTS insights_cache (
    key TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    role TEXT NOT NULL,
    run_id TEXT NOT NULL,
    json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
""")


def _h(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:24]


def content_version() -> str:
    """Меняется при появлении новых новостей, фактов или материалов аналитики."""
    with session() as conn:
        news = conn.execute("SELECT COUNT(*), MAX(published_at), GROUP_CONCAT(hash) FROM news_items").fetchone()
        theses = conn.execute("SELECT COUNT(*), GROUP_CONCAT(thesis_id || quote) FROM theses").fetchone()
        facts = conn.execute("SELECT COUNT(*) FROM news_facts").fetchone()
    return _h(tuple(news), tuple(theses), tuple(facts))


def profile_version(company_id: str) -> str:
    """Меняется при изменении данных компании или её платежей."""
    with session() as conn:
        row = conn.execute("SELECT * FROM companies WHERE company_id = ?", (company_id,)).fetchone()
        pay = conn.execute("SELECT COUNT(*), SUM(amount) FROM payments WHERE payer = ? OR beneficiary = ?",
                           (company_id, company_id)).fetchone()
    return _h(dict(row) if row else None, tuple(pay))


def cache_key(company_id: str, event_id: str, role: str) -> str:
    return _h(company_id, event_id, role, interpreter.PROMPT_VERSION, planner.PROMPT_VERSION, settings.llm_mode,
              profile_version(company_id), content_version())


def get_or_run(company_id: str, event_id: str, role: str = "cfo", on_step=None) -> tuple[Insight, bool]:
    """Инсайт из кэша (cached=True) или новый запуск оркестратора."""
    key = cache_key(company_id, event_id, role)
    with session() as conn:
        row = conn.execute("SELECT json FROM insights_cache WHERE key = ?", (key,)).fetchone()
    if row:
        return Insight.model_validate_json(row["json"]), True
    state = run_insight(company_id, event_id, role, on_step=on_step)
    if state.insight.status == "FALLBACK":  # сбой модели (таймаут, бюджет) не закрепляется: следующий запрос повторит
        return state.insight, False
    with session() as conn:
        conn.execute("INSERT OR REPLACE INTO insights_cache (key, company_id, event_id, role, run_id, json, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (key, company_id, event_id, role, state.run_id, state.insight.model_dump_json(),
                      datetime.now(timezone.utc).isoformat()))
    return state.insight, False
