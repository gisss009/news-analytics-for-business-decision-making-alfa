"""Офлайн-загрузка контента: новости из источников (сейчас FixtureSource) и аналитика банка из тезисов-фикстур.

STUB-части: FixtureSource вместо сбора новостей; data/analytics/fixtures/theses.json вместо разбора PDF
(страница в analytics_pages содержит только перенесённые вручную фрагменты, excerpt_only=1).
Повторный запуск идемпотентен. Запуск: python -m app.ingest.offline
"""
import hashlib
import json
import re
from pathlib import Path

from app.core.config import settings
from app.core.db import session
from app.ingest import store  # noqa: F401  (регистрирует таблицы)
from app.ingest.sources.base import Source
from app.ingest.sources.fixtures import FixtureSource


def text_hash(text: str) -> str:
    norm = re.sub(r"\s+", " ", text.lower()).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def load_news(sources: list[Source]) -> dict:
    n = 0
    with session() as conn:
        for src in sources:
            for link in src.fetch_list():
                a = src.fetch_article(link)
                conn.execute(
                    "INSERT OR REPLACE INTO news_items (item_id, url, title, text, published_at, source_name, "
                    "source_type, hash, synthetic, holdout) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (a.item_id, a.url, a.title, a.text, a.published_at.isoformat(), a.source_name, a.source_type,
                     text_hash(a.text), int(a.synthetic), int(a.holdout)))
                n += 1
    return {"news": n}


def analytics_fixture_path() -> Path:
    return settings.data_dir / "analytics" / "fixtures" / "theses.json"


def load_analytics(path: Path | None = None) -> dict:
    path = path or analytics_fixture_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    pdf_dir = path.parent.parent
    docs = theses = 0
    with session() as conn:
        conn.execute("DELETE FROM theses")
        conn.execute("DELETE FROM analytics_pages")
        conn.execute("DELETE FROM analytics_docs")
        for d in data["documents"]:
            conn.execute("INSERT INTO analytics_docs (doc_id, title, date, kind, file, stale, file_present) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (d["doc_id"], d["title"], d["date"], d["kind"], d.get("file"), int(d.get("stale", False)),
                          int(bool(d.get("file")) and (pdf_dir / d["file"]).exists())))
            pages: dict[int, list[str]] = {}
            for k, t in enumerate(d["theses"], start=1):
                pages.setdefault(t["page"], []).append(t["quote"])
                conn.execute("INSERT INTO theses (thesis_id, doc_id, page, topic, horizon, text, quote) "
                             "VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (f"{d['doc_id']}#t{k}", d["doc_id"], t["page"], t["topic"], t.get("horizon"),
                              t["thesis"], t["quote"]))
                theses += 1
            for page, quotes in pages.items():
                conn.execute("INSERT INTO analytics_pages (doc_id, page, text, excerpt_only) VALUES (?, ?, ?, 1)",
                             (d["doc_id"], page, " […] ".join(quotes)))
            docs += 1
    return {"analytics_docs": docs, "theses": theses}


def run(include_holdout: bool = True) -> dict:
    """Полный офлайн-конвейер. Следующие шаги (дедупликация, классификация, факты, индекс) добавляются сюда."""
    stats = load_news([FixtureSource(include_holdout=include_holdout)])
    stats.update(load_analytics())
    return stats


if __name__ == "__main__":
    print(run())
