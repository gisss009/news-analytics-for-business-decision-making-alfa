"""Единый поисковый слой по новостям и аналитике банка: BM25 (SQLite FTS5) с русской нормализацией и фильтрами.

FTS5 не умеет русский стемминг, поэтому в индекс пишется текст, уже приведённый к основам (Snowball),
а запрос нормализуется так же. Эмбеддинги не используются (в списке разрешённых моделей нет модели эмбеддингов);
интерфейс Retriever позволяет добавить их позже.
Запуск: python -m app.ingest.index "ключевая ставка" [news|analytics]
"""
import json
import sqlite3
import sys
from typing import Literal, Protocol

from pydantic import BaseModel

from app.core.db import register_schema, session
from app.ingest.text import stems

Kind = Literal["news", "analytics"]

register_schema("search_fts", """
CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
    body,
    ref UNINDEXED, kind UNINDEXED, topic UNINDEXED, sectors UNINDEXED, date UNINDEXED,
    source_type UNINDEXED, title UNINDEXED, snippet UNINDEXED, extra UNINDEXED,
    tokenize = 'unicode61'
);
""")


class Filters(BaseModel):
    topic: str | None = None
    sector: str | None = None
    date_from: str | None = None   # ISO, включительно
    date_to: str | None = None     # ISO, включительно (сравнение по префиксу даты)
    source_type: str | None = None  # news | blog | bank_analytics
    include_holdout: bool = True
    include_stale: bool = False


class Hit(BaseModel):
    ref: str
    kind: Kind
    title: str
    snippet: str
    score: float
    topic: str | None = None
    sectors: list[str] = []
    date: str | None = None
    extra: dict = {}


class Retriever(Protocol):
    def search(self, query: str, kind: Kind, filters: Filters | None = None, k: int = 5) -> list[Hit]: ...


def _norm(text: str) -> str:
    return " ".join(stems(text))


def build() -> dict:
    """Пересобирает индекс из news_items/news_class/clusters и theses/analytics_docs. Идемпотентно."""
    with session() as conn:
        conn.execute("DELETE FROM search_fts")
        news = conn.execute(
            "SELECT n.item_id, n.title, n.text, n.published_at, n.source_type, n.source_name, n.holdout, "
            "c.topic, c.sectors, ci.event_id FROM news_items n LEFT JOIN news_class c USING (item_id) "
            "LEFT JOIN cluster_items ci USING (item_id)").fetchall()
        for r in news:
            conn.execute(
                "INSERT INTO search_fts (body, ref, kind, topic, sectors, date, source_type, title, snippet, extra) "
                "VALUES (?, ?, 'news', ?, ?, ?, ?, ?, ?, ?)",
                (_norm(f"{r['title']} {r['title']} {r['text']}"), f"news:{r['item_id']}", r["topic"], r["sectors"] or "[]",
                 r["published_at"], r["source_type"], r["title"], r["text"][:300],
                 json.dumps({"event_id": r["event_id"], "source_name": r["source_name"], "holdout": bool(r["holdout"])},
                            ensure_ascii=False)))
        theses = conn.execute(
            "SELECT t.*, d.title AS doc_title, d.date AS doc_date, d.stale FROM theses t "
            "JOIN analytics_docs d USING (doc_id)").fetchall()
        for t in theses:
            conn.execute(
                "INSERT INTO search_fts (body, ref, kind, topic, sectors, date, source_type, title, snippet, extra) "
                "VALUES (?, ?, 'analytics', ?, '[]', ?, 'bank_analytics', ?, ?, ?)",
                (_norm(f"{t['text']} {t['quote']} {t['doc_title']}"), f"doc:{t['doc_id']}#p{t['page']}", t["topic"],
                 t["doc_date"], t["doc_title"], t["quote"],
                 json.dumps({"thesis_id": t["thesis_id"], "thesis": t["text"], "horizon": t["horizon"],
                             "stale": bool(t["stale"])}, ensure_ascii=False)))
    return {"indexed_news": len(news), "indexed_theses": len(theses)}


class BM25Retriever:
    def search(self, query: str, kind: Kind, filters: Filters | None = None, k: int = 5) -> list[Hit]:
        f = filters or Filters()
        tokens = sorted(set(stems(query)))
        if not tokens:
            return []
        match = " OR ".join(f'"{t}"' for t in tokens)
        sql = ["SELECT ref, kind, title, snippet, topic, sectors, date, extra, bm25(search_fts) AS rank FROM search_fts "
               "WHERE search_fts MATCH ? AND kind = ?"]
        args: list = [match, kind]
        if f.topic:
            sql.append("AND topic = ?"); args.append(f.topic)
        if f.sector:
            sql.append("AND sectors LIKE ?"); args.append(f'%"{f.sector}"%')
        if f.date_from:
            sql.append("AND date >= ?"); args.append(f.date_from)
        if f.date_to:
            sql.append("AND substr(date, 1, ?) <= ?"); args += [len(f.date_to), f.date_to]
        if f.source_type:
            sql.append("AND source_type = ?"); args.append(f.source_type)
        sql.append("ORDER BY rank LIMIT ?")
        args.append(k * 3)  # запас на фильтры по extra
        with session() as conn:
            try:
                rows = conn.execute(" ".join(sql), args).fetchall()
            except sqlite3.OperationalError:
                return []
        hits = []
        for r in rows:
            extra = json.loads(r["extra"] or "{}")
            if not f.include_holdout and extra.get("holdout"):
                continue
            if not f.include_stale and extra.get("stale"):
                continue
            hits.append(Hit(ref=r["ref"], kind=r["kind"], title=r["title"], snippet=r["snippet"],
                            score=round(-r["rank"], 4), topic=r["topic"], sectors=json.loads(r["sectors"] or "[]"),
                            date=r["date"], extra=extra))
        return hits[:k]


retriever: Retriever = BM25Retriever()


def search(query: str, kind: Kind = "news", filters: Filters | None = None, k: int = 5) -> list[Hit]:
    return retriever.search(query, kind, filters, k)


if __name__ == "__main__":
    for h in search(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "news"):
        print(f"{h.score:7.3f}  {h.ref:<34} {h.topic or '-':<16} {h.title[:70]}")
