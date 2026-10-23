"""Режим real в ingest: вызовы модели идут вне транзакций записи (клиент LLM пишет бюджет и кэш в ту же БД)."""
import json

import httpx

from app.core.db import connect
from app.ingest import analytics_chunk, classify, offline
from app.llm import client
from tests.unit.test_analytics_chunk import doc
from tests.unit.test_llm_client import real_mode  # noqa: F401  (фикстура)


def provider(monkeypatch):
    calls = []

    def handler(req: httpx.Request):
        body = json.loads(req.content)
        calls.append(body)
        data = client.extract_data(body["messages"])
        if "items" in data:
            content = {"items": [{"id": i["id"], "thesis": "Тезис: " + i["text"][:60]} for i in data["items"]]}
        else:
            content = {"topic": "rate", "confidence": 0.9}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}],
                                         "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
    monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
    return calls


def test_classify_run_records_budget_without_lock(real_mode, monkeypatch):  # noqa: F811
    calls = provider(monkeypatch)
    offline.load_news([offline.FixtureSource(include_holdout=False)])
    s = classify.run()
    conn = connect()
    assert s["methods"] == {"llm": s["classified"]} and len(calls) == s["classified"]
    assert conn.execute("SELECT COUNT(*) FROM llm_usage").fetchone()[0] >= 1


def test_thesis_rewrite_in_batches_without_lock(real_mode, monkeypatch):  # noqa: F811
    calls = provider(monkeypatch)
    s = analytics_chunk.load_from_pdfs([doc()])
    rows = connect().execute("SELECT text, quote FROM theses").fetchall()
    assert len(rows) == s["theses"] and all(r["text"].startswith("Тезис: ") for r in rows)
    assert all(len(client.extract_data(c["messages"])["items"]) <= analytics_chunk.REWRITE_BATCH
               for c in calls)
    assert len(calls) == -(-s["theses"] // analytics_chunk.REWRITE_BATCH)
