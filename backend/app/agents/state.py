"""Общий контекст запуска (RunState): всё, что видят шаги одного запуска, follow-up и трассировка.

Хранится в таблице runs как JSON; восстанавливается по run_id в любом процессе.
"""
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, PrivateAttr

from app.agents.schemas import Insight, Plan, Relevance, TraceStep, Verification
from app.core.db import register_schema, session

register_schema("runs", """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    event_id TEXT,
    status TEXT NOT NULL,
    json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_runs_company ON runs(company_id);
""")

RunStatus = Literal["CREATED", "PLANNED", "RETRIEVED", "RANKED", "INTERPRETED", "VERIFYING", "DONE",
                    "DONE_WITH_WARNINGS", "FALLBACK", "ERROR"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ToolResult(BaseModel):
    step: str
    tool: str
    args: dict = {}
    ok: bool = True
    result: dict | list | None = None
    error: str | None = None


class RunState(BaseModel):
    run_id: str = Field(default_factory=lambda: f"r_{uuid.uuid4().hex[:12]}")
    company_id: str
    role: str = "cfo"
    event_id: str | None = None
    status: RunStatus = "CREATED"
    plan: Plan | None = None
    tool_results: list[ToolResult] = []
    context: dict = {}            # промежуточные данные шагов (событие, профиль, позиция банка)
    relevance: Relevance | None = None
    insight: Insight | None = None
    verifications: list[Verification] = []
    iterations: int = 0
    trace: list[TraceStep] = []
    warnings: list[str] = []
    tokens_used: int = 0
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    _on_step: object = PrivateAttr(default=None)  # необязательный слушатель шагов (прогресс для UI)

    def on_step(self, callback) -> None:
        self._on_step = callback

    @contextmanager
    def step(self, name: str, **detail):
        """Записывает шаг в трассу: время, длительность, статус. Внутри блока detail можно дополнять."""
        started, t0 = _now(), time.perf_counter()
        info = dict(detail)
        status = "ok"
        try:
            yield info
            status = info.pop("_status", "ok")
        except Exception as e:
            status = "error"
            info["error"] = str(e)[:300]
            raise
        finally:
            ts = TraceStep(step=name, status=status, started_at=started,
                           duration_ms=int((time.perf_counter() - t0) * 1000), detail=info)
            self.trace.append(ts)
            if callable(self._on_step):
                self._on_step(ts)


def save(state: RunState) -> None:
    state.updated_at = _now()
    with session() as conn:
        conn.execute(
            "INSERT INTO runs (run_id, company_id, event_id, status, json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(run_id) DO UPDATE SET status = excluded.status, "
            "json = excluded.json, updated_at = excluded.updated_at",
            (state.run_id, state.company_id, state.event_id, state.status, state.model_dump_json(),
             state.created_at.isoformat(), state.updated_at.isoformat()))


class RunNotFound(LookupError):
    pass


def load(run_id: str) -> RunState:
    with session() as conn:
        row = conn.execute("SELECT json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        raise RunNotFound(run_id)
    return RunState.model_validate_json(row["json"])
