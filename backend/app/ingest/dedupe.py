"""Поиск почти-дубликатов и объединение новостей в события (кластеры).

Похожесть пары = w1·Jaccard(основы слов) + w2·Jaccard(числа), только для новостей в окне window_hours.
Кластеры — связные компоненты графа похожих пар (union-find). Событие: заголовок и время самой ранней
публикации, список источников. Пары перебираются полностью (O(n²)) — достаточно для сотен новостей в сутки;
для больших потоков заменить на MinHash/LSH с тем же интерфейсом cluster().
"""
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import yaml

from app.core.db import register_schema, session
from app.ingest.text import numbers, stems

CONFIG_PATH = Path(__file__).resolve().parent / "ingest.yaml"

register_schema("clusters", """
CREATE TABLE IF NOT EXISTS clusters (
    event_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    size INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cluster_items (
    event_id TEXT NOT NULL,
    item_id TEXT NOT NULL PRIMARY KEY
);
CREATE INDEX IF NOT EXISTS ix_cluster_items_event ON cluster_items(event_id);
""")


@lru_cache
def config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dedupe"]


@dataclass
class Item:
    item_id: str
    title: str
    text: str
    published_at: datetime
    source_name: str = ""


@dataclass
class Cluster:
    event_id: str
    item_ids: list[str]
    title: str
    first_seen: datetime
    sources: list[str] = field(default_factory=list)


def similarity(a: Item, b: Item, cfg: dict | None = None) -> float:
    cfg = cfg or config()
    sa, sb = set(stems(f"{a.title} {a.text}")), set(stems(f"{b.title} {b.text}"))
    na, nb = numbers(f"{a.title} {a.text}"), numbers(f"{b.title} {b.text}")
    jw = len(sa & sb) / len(sa | sb) if sa | sb else 0.0
    jn = len(na & nb) / len(na | nb) if na | nb else 0.0
    return cfg["weight_words"] * jw + cfg["weight_numbers"] * jn


def cluster(items: list[Item], cfg: dict | None = None) -> list[Cluster]:
    cfg = cfg or config()
    items = sorted(items, key=lambda i: (i.published_at, i.item_id))
    parent = {i.item_id: i.item_id for i in items}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for k, a in enumerate(items):
        for b in items[k + 1:]:
            if (b.published_at - a.published_at).total_seconds() > cfg["window_hours"] * 3600:
                break
            if similarity(a, b, cfg) >= cfg["threshold"]:
                parent[find(b.item_id)] = find(a.item_id)

    groups: dict[str, list[Item]] = {}
    for i in items:
        groups.setdefault(find(i.item_id), []).append(i)
    out = []
    for members in groups.values():
        first = members[0]  # уже отсортированы по времени
        out.append(Cluster(event_id=f"ev_{first.item_id}", item_ids=[m.item_id for m in members], title=first.title,
                           first_seen=first.published_at, sources=sorted({m.source_name for m in members})))
    return sorted(out, key=lambda c: c.first_seen)


def run() -> dict:
    """Перекластеризация всех news_items в таблицы clusters / cluster_items (идемпотентно)."""
    with session() as conn:
        rows = conn.execute("SELECT item_id, title, text, published_at, source_name FROM news_items").fetchall()
        items = [Item(r["item_id"], r["title"], r["text"], datetime.fromisoformat(r["published_at"]), r["source_name"])
                 for r in rows]
        clusters = cluster(items)
        conn.execute("DELETE FROM cluster_items")
        conn.execute("DELETE FROM clusters")
        for c in clusters:
            conn.execute("INSERT INTO clusters (event_id, title, first_seen, size) VALUES (?, ?, ?, ?)",
                         (c.event_id, c.title, c.first_seen.isoformat(), len(c.item_ids)))
            conn.executemany("INSERT INTO cluster_items (event_id, item_id) VALUES (?, ?)",
                             [(c.event_id, i) for i in c.item_ids])
    return {"items": len(items), "events": len(clusters), "merged": len(items) - len(clusters)}


def pair_metrics(items: list[Item], gold_root: dict[str, str]) -> dict:
    """Precision/recall по парам «в одном кластере» против эталона (gold_root: item_id → корень дубля)."""
    pred_root = {i: c.event_id for c in cluster(items) for i in c.item_ids}
    ids = sorted(gold_root)
    tp = fp = fn = 0
    for k, a in enumerate(ids):
        for b in ids[k + 1:]:
            p, g = pred_root[a] == pred_root[b], gold_root[a] == gold_root[b]
            tp += p and g
            fp += p and not g
            fn += g and not p
    return {"precision": tp / (tp + fp) if tp + fp else 1.0, "recall": tp / (tp + fn) if tp + fn else 1.0,
            "pairs_tp": tp, "pairs_fp": fp, "pairs_fn": fn}


if __name__ == "__main__":
    from app.ingest.fixtures import load_fixtures
    fx = load_fixtures(include_holdout=True)
    items = [Item(i.id, i.title, i.text, i.published_at, i.source.name) for i in fx]
    print(pair_metrics(items, {i.id: i.gold.duplicate_of or i.id for i in fx}))
