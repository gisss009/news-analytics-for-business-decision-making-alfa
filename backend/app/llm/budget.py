"""Дневной бюджет LLM (DAILY_BUDGET_RUB) и кэш ответов. Используется только из llm/client.py."""
import hashlib
import json
from datetime import datetime, timezone

from app.core.config import model_routing, settings
from app.core.db import register_schema, session
from app.core.logging import get_logger
from app.llm.errors import BudgetExceeded

register_schema("llm_budget", """
CREATE TABLE IF NOT EXISTS llm_usage (
    day TEXT NOT NULL,
    model TEXT NOT NULL,
    mode TEXT NOT NULL,
    calls INTEGER NOT NULL DEFAULT 0,
    tokens INTEGER NOT NULL DEFAULT 0,
    rub REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (day, model, mode)
);
CREATE TABLE IF NOT EXISTS llm_cache (
    key TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    response TEXT NOT NULL,
    created TEXT NOT NULL
);
""")

log = get_logger("budget")


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def cost_rub(model: str, tokens: int) -> float:
    price = model_routing()["prices_rub_per_1k"][model]
    return tokens / 1000 * price


def spent_today() -> float:
    with session() as conn:
        row = conn.execute("SELECT COALESCE(SUM(rub), 0) AS s FROM llm_usage WHERE day = ?", (today(),)).fetchone()
    return float(row["s"])


def status() -> dict:
    spent = spent_today()
    return {"day": today(), "spent_rub": round(spent, 4), "limit_rub": settings.daily_budget_rub,
            "ratio": round(spent / settings.daily_budget_rub, 4) if settings.daily_budget_rub else 1.0}


def check_and_reserve(model: str, est_tokens: int) -> None:
    """Отказ, если вызов с оценкой est_tokens выведет за дневной лимит; предупреждение с 80%."""
    spent = spent_today()
    limit = settings.daily_budget_rub
    projected = spent + cost_rub(model, est_tokens)
    if spent >= limit or projected > limit:
        raise BudgetExceeded(f"Дневной бюджет LLM исчерпан: потрачено {spent:.2f} из {limit:.2f} руб. "
                             f"Вызов отклонён, используется запасной вариант.")
    if projected >= limit * settings.budget_warn_ratio:
        log.warning("budget_warning", extra={"spent_rub": round(projected, 2), "limit_rub": limit})


def record(model: str, tokens: int, mode: str) -> None:
    rub = cost_rub(model, tokens) if mode == "real" else 0.0
    with session() as conn:
        conn.execute(
            "INSERT INTO llm_usage (day, model, mode, calls, tokens, rub) VALUES (?, ?, ?, 1, ?, ?) "
            "ON CONFLICT(day, model, mode) DO UPDATE SET calls = calls + 1, tokens = tokens + excluded.tokens, "
            "rub = rub + excluded.rub", (today(), model, mode, tokens, rub))


def cache_key(model: str, messages: list[dict], temperature: float, schema_name: str | None) -> str:
    raw = json.dumps([model, messages, temperature, schema_name], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_get(key: str) -> str | None:
    with session() as conn:
        row = conn.execute("SELECT response FROM llm_cache WHERE key = ?", (key,)).fetchone()
    return row["response"] if row else None


def cache_put(key: str, model: str, response: str) -> None:
    with session() as conn:
        conn.execute("INSERT OR REPLACE INTO llm_cache (key, model, response, created) VALUES (?, ?, ?, ?)",
                     (key, model, response, datetime.now(timezone.utc).isoformat()))
