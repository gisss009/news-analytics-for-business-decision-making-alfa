"""Сбор новостей из источников в news_items: дата в UTC, URL, хэш текста, без дублей.

Сбой одного источника или одной статьи не останавливает остальные. Текст новостей — данные, а не инструкции.
Запуск: python -m app.ingest.fetch [fixtures|live]
"""
import hashlib
import re
import sys
from datetime import timezone

from app.core.db import session
from app.core.logging import get_logger
from app.ingest import store  # noqa: F401  (регистрирует таблицы)
from app.ingest.sources.base import Source

log = get_logger("ingest.fetch")

EXTRA_COLUMNS = {"topic_hint": "TEXT", "text_status": "TEXT NOT NULL DEFAULT 'full'"}


def text_hash(text: str) -> str:
    norm = re.sub(r"\s+", " ", text.lower()).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def ensure_columns(conn) -> None:
    """Миграция: новые столбцы news_items для баз, созданных до живых источников."""
    have = {r["name"] for r in conn.execute("PRAGMA table_info(news_items)")}
    for name, ddl in EXTRA_COLUMNS.items():
        if name not in have:
            conn.execute(f"ALTER TABLE news_items ADD COLUMN {name} {ddl}")


def run(sources: list[Source]) -> dict:
    stats = {"fetched": 0, "new": 0, "updated": 0, "duplicates": 0, "errors": 0}
    with session() as conn:
        ensure_columns(conn)
        hashes = {r["hash"]: r["item_id"] for r in conn.execute("SELECT item_id, hash FROM news_items")}
        known = set(hashes.values())
        for src in sources:
            try:
                links = src.fetch_list()
            except Exception as e:  # noqa: BLE001 — сбой источника: остальные продолжают
                stats["errors"] += 1
                log.warning("source_failed", extra={"source": src.name, "error": str(e)[:200]})
                continue
            stats["errors"] += len(getattr(src, "errors", []))
            for link in links:
                try:
                    a = src.fetch_article(link)
                except Exception as e:  # noqa: BLE001
                    stats["errors"] += 1
                    log.warning("article_failed", extra={"url": link.url[:120], "error": str(e)[:200]})
                    continue
                stats["fetched"] += 1
                h = text_hash(a.text)
                if h in hashes and hashes[h] != a.item_id:  # тот же текст под другим адресом
                    stats["duplicates"] += 1
                    continue
                published = a.published_at.astimezone(timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO news_items (item_id, url, title, text, published_at, source_name, source_type, hash, "
                    "synthetic, holdout, topic_hint, text_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(item_id) DO UPDATE SET title = excluded.title, text = excluded.text, "
                    "hash = excluded.hash, text_status = excluded.text_status, topic_hint = excluded.topic_hint",
                    (a.item_id, a.url, a.title, a.text, published, a.source_name, a.source_type, h, int(a.synthetic),
                     int(a.holdout), a.topic_hint, a.text_status))
                stats["updated" if a.item_id in known else "new"] += 1
                known.add(a.item_id)
                hashes[h] = a.item_id
    return stats


def remove_synthetic() -> int:
    """Убирает вымышленные новости офлайн-набора (режим живых новостей)."""
    with session() as conn:
        ensure_columns(conn)
        return conn.execute("DELETE FROM news_items WHERE synthetic = 1").rowcount


if __name__ == "__main__":
    from app.ingest.sources.fixtures import registry
    name = sys.argv[1] if len(sys.argv) > 1 else "fixtures"
    print(run([registry()[name]()]))
