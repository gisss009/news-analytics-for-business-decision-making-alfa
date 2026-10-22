"""Таблицы контента: новости и материалы аналитики банка (docs/ARCHITECTURE.md §6)."""
from app.core.db import register_schema

register_schema("ingest_content", """
CREATE TABLE IF NOT EXISTS news_items (
    item_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    published_at TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    hash TEXT NOT NULL,
    synthetic INTEGER NOT NULL DEFAULT 0,
    holdout INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS analytics_docs (
    doc_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    kind TEXT NOT NULL,
    file TEXT,
    stale INTEGER NOT NULL DEFAULT 0,
    file_present INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS analytics_pages (
    doc_id TEXT NOT NULL,
    page INTEGER NOT NULL,
    text TEXT NOT NULL,
    excerpt_only INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (doc_id, page)
);
CREATE TABLE IF NOT EXISTS theses (
    thesis_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    page INTEGER NOT NULL,
    topic TEXT NOT NULL,
    horizon TEXT,
    text TEXT NOT NULL,
    quote TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_theses_topic ON theses(topic);
""")
