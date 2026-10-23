"""Офлайн-загрузка контента: новости из источников (сейчас FixtureSource) и аналитика банка из тезисов-фикстур.

STUB-части: FixtureSource вместо сбора новостей; data/analytics/fixtures/theses.json вместо разбора PDF
(страница в analytics_pages содержит только перенесённые вручную фрагменты, excerpt_only=1).
Повторный запуск идемпотентен. Запуск: python -m app.ingest.offline
"""
import json
from pathlib import Path

from app.core.config import settings
from app.core.db import session
from app.ingest import classify, dedupe, facts, fetch, index, store  # noqa: F401  (store регистрирует таблицы)
from app.ingest.sources.base import Source
from app.ingest.sources.fixtures import FixtureSource


def load_news(sources: list[Source]) -> dict:
    stats = fetch.run(sources)
    return {"news": stats["new"] + stats["updated"], "news_duplicates": stats["duplicates"],
            "news_errors": stats["errors"]}


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
    """Полный офлайн-конвейер: загрузка → дедупликация → классификация → факты → индекс."""
    stats = load_news([FixtureSource(include_holdout=include_holdout)])
    stats.update(load_analytics())
    stats.update(dedupe.run())
    stats.update(classify.run())
    stats.update(facts.run())
    stats.update(index.build())
    return stats


if __name__ == "__main__":
    print(run())
