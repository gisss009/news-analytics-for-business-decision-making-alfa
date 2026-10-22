"""Чтение событий (кластеров новостей) со всеми материалами, классификацией и фактами."""
import json
from datetime import datetime

from app.core.db import session
from app.ingest import dedupe, store  # noqa: F401  (регистрирует таблицы)


class EventNotFound(LookupError):
    pass


def _event_from_rows(conn, ev) -> dict:
    items = []
    for r in conn.execute(
            "SELECT n.*, c.topic, c.sectors, c.geo, c.entities, c.confidence AS class_conf FROM cluster_items ci "
            "JOIN news_items n USING (item_id) LEFT JOIN news_class c USING (item_id) "
            "WHERE ci.event_id = ? ORDER BY n.published_at, n.item_id", (ev["event_id"],)):
        facts = [{"fact_id": f["fact_id"], "values": json.loads(f["vals"]), "date": f["date"], "quote": f["quote"],
                  "modality": f["modality"]}
                 for f in conn.execute("SELECT * FROM news_facts WHERE item_id = ? ORDER BY n", (r["item_id"],))]
        items.append({"item_id": r["item_id"], "title": r["title"], "text": r["text"], "url": r["url"],
                      "published_at": r["published_at"], "source_name": r["source_name"],
                      "source_type": r["source_type"], "holdout": bool(r["holdout"]), "topic": r["topic"] or "other",
                      "sectors": json.loads(r["sectors"] or "[]"), "geo": json.loads(r["geo"] or "[]"),
                      "entities": json.loads(r["entities"] or "[]"), "facts": facts})
    lead = items[0]
    return {"event_id": ev["event_id"], "title": ev["title"], "first_seen": ev["first_seen"], "size": ev["size"],
            "topic": lead["topic"], "sectors": sorted({s for i in items for s in i["sectors"]}),
            "geo": sorted({g for i in items for g in i["geo"]}), "items": items,
            "source_types": sorted({i["source_type"] for i in items}), "holdout": all(i["holdout"] for i in items)}


def get_event(event_id: str) -> dict:
    with session() as conn:
        ev = conn.execute("SELECT * FROM clusters WHERE event_id = ?", (event_id,)).fetchone()
        if ev is None:
            raise EventNotFound(event_id)
        return _event_from_rows(conn, ev)


def list_events() -> list[dict]:
    with session() as conn:
        return [_event_from_rows(conn, ev) for ev in conn.execute("SELECT * FROM clusters ORDER BY first_seen DESC")]


def now_for_demo() -> datetime:
    """«Текущий момент» для свежести: время самой поздней новости (данные офлайн и не обновляются)."""
    with session() as conn:
        row = conn.execute("SELECT MAX(published_at) FROM news_items").fetchone()
    return datetime.fromisoformat(row[0])
