"""JSON-логи, run_id в контексте, маскирование и журнал вызовов инструментов и моделей (tool_calls)."""
import contextvars
import hashlib
import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.db import connect, register_schema

run_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("run_id", default=None)

register_schema("tool_calls", """
CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    tool TEXT NOT NULL,
    args_masked TEXT NOT NULL,
    result_hash TEXT,
    tokens INTEGER NOT NULL DEFAULT 0,
    ok INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tool_calls_run ON tool_calls(run_id);
""")

SENSITIVE_KEYS = {"api_key", "llm_api_key", "authorization", "token", "password", "secret"}
MASK_MIN_LEN = 12  # строки-идентификаторы длиннее этого маскируются частично
_ID_LIKE = re.compile(r"^[A-Za-z0-9_\-]+$")


def mask(value: Any) -> Any:
    """Маскирует секреты и длинные идентификаторы перед логированием. Обычный текст не трогает."""
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in SENSITIVE_KEYS else mask(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [mask(v) for v in value]
    if isinstance(value, str) and len(value) > MASK_MIN_LEN and _ID_LIKE.match(value):
        return f"{value[:3]}***{value[-2:]}"
    return value


def result_hash(result: Any) -> str:
    raw = json.dumps(result, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def log_tool_call(actor: str, tool: str, args: Any, result: Any = None, tokens: int = 0, ok: bool = True,
                  conn: sqlite3.Connection | None = None) -> None:
    """Пишет вызов инструмента или модели в tool_calls и в лог."""
    args_masked = json.dumps(mask(args), ensure_ascii=False, default=str)
    row = (run_id_var.get(), datetime.now(timezone.utc).isoformat(), actor, tool, args_masked,
           result_hash(result), tokens, int(ok))
    own = conn is None
    conn = conn or connect()
    try:
        conn.execute("INSERT INTO tool_calls (run_id, ts, actor, tool, args_masked, result_hash, tokens, ok) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", row)
        conn.commit()
    finally:
        if own:
            conn.close()
    get_logger("tool_calls").info("tool_call", extra={"actor": actor, "tool": tool, "tokens": tokens, "ok": ok})


class JsonFormatter(logging.Formatter):
    _std = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message"}

    def format(self, record: logging.LogRecord) -> str:
        data = {"ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(), "level": record.levelname,
                "logger": record.name, "msg": record.getMessage(), "run_id": run_id_var.get()}
        data.update({k: mask(v) for k, v in record.__dict__.items() if k not in self._std})
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


_configured = False


def get_logger(name: str) -> logging.Logger:
    global _configured
    if not _configured:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root = logging.getLogger("app")
        root.addHandler(handler)
        root.setLevel(settings.log_level)
        root.propagate = False
        _configured = True
    return logging.getLogger(f"app.{name}")
