"""Одна SQLite-БД на приложение. Модули регистрируют свои таблицы через register_schema()."""
import sqlite3
import threading
from pathlib import Path

from app.core.config import settings

_SCHEMAS: dict[str, str] = {}
_applied: dict[str, set[str]] = {}
_lock = threading.Lock()


def register_schema(name: str, ddl: str) -> None:
    """DDL должен быть идемпотентным (CREATE ... IF NOT EXISTS)."""
    _SCHEMAS[name] = ddl


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Открывает соединение и применяет ещё не применённые схемы."""
    path = str(db_path or settings.db_path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    with _lock:
        done = _applied.setdefault(path, set()) if path != ":memory:" else set()
        for name, ddl in _SCHEMAS.items():
            if name not in done:
                conn.executescript(ddl)
                done.add(name)
    return conn
