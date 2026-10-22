from datetime import datetime, timedelta, timezone

from app.core.db import connect
from app.ingest import offline
from app.ingest.dedupe import Item, cluster, pair_metrics, run
from app.ingest.fixtures import load_fixtures


def fixture_items():
    fx = load_fixtures(include_holdout=True)
    return [Item(i.id, i.title, i.text, i.published_at, i.source.name) for i in fx], \
        {i.id: i.gold.duplicate_of or i.id for i in fx}


def test_known_duplicates_clustered_with_high_precision_recall():
    items, gold = fixture_items()
    m = pair_metrics(items, gold)
    print("dedupe metrics on fixtures:", m)
    assert m["precision"] >= 0.9 and m["recall"] >= 0.9


def test_rate_event_merges_three_sources():
    items, _ = fixture_items()
    ev = next(c for c in cluster(items) if "n001" in c.item_ids)
    assert ev.item_ids == ["n001", "n002", "n003"] and ev.event_id == "ev_n001" and len(ev.sources) == 3


def test_time_window_respected():
    t = datetime(2026, 9, 1, tzinfo=timezone.utc)
    a = Item("a", "Ставка 14%", "Банк России сохранил ключевую ставку 14% годовых", t)
    b = Item("b", "Ставка 14%", "Банк России сохранил ключевую ставку 14% годовых", t + timedelta(days=5))
    assert len(cluster([a, b])) == 2
    assert len(cluster([a, Item("c", a.title, a.text, t + timedelta(hours=3))])) == 1


def test_run_writes_tables_idempotently():
    offline.load_news([offline.FixtureSource()])
    s1, s2 = run(), run()
    assert s1 == s2 and s1["merged"] == 5
    assert connect().execute("SELECT COUNT(*) FROM cluster_items").fetchone()[0] == s1["items"]
