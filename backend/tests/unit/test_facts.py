from app.core.db import connect
from app.ingest import offline
from app.ingest.facts import extract
from app.ingest.fixtures import load_fixtures
from app.ingest.text import numbers


def all_facts():
    return [(i, f) for i in load_fixtures(include_holdout=True) for f in extract(i.id, i.text, 2026)]


def test_every_quote_is_exact_substring_and_values_match():
    pairs = all_facts()
    assert len(pairs) >= 80
    for item, f in pairs:
        assert item.text[f.span[0]:f.span[1]] == f.quote, f.fact_id
        for v in f.values:
            assert v in f.quote
            assert numbers(v) <= numbers(f.quote), (f.fact_id, v)


def test_key_rate_fact():
    fx = {i.id: i for i in load_fixtures()}
    facts = extract("n001", fx["n001"].text, 2026)
    first = facts[0]
    assert first.fact_id == "news:n001#f1" and first.subject == "Банк России"
    assert first.date == "2026-09-11" and any(v.startswith("14,0%") for v in first.values)
    assert first.modality == "stated"
    assert any(f.date == "2026-10-23" for f in facts)


def test_modality():
    fx = {i.id: i for i in load_fixtures()}
    spec = extract("n043", fx["n043"].text, 2026)
    assert any(f.modality == "speculation" for f in spec)
    planned = extract("n034", fx["n034"].text, 2026)
    assert planned[0].modality == "expected"


def test_sentence_split_keeps_abbreviations():
    facts = extract("x", "За январь–август 2026 года ввели 61 млн кв. м жилья, что на 9% меньше. Второе предложение.", 2026)
    assert len(facts) == 1 and "кв. м жилья" in facts[0].quote and facts[0].date == "2026"


def test_pipeline_writes_facts():
    s = offline.run()
    assert s["facts"] > 0
    assert connect().execute("SELECT COUNT(*) FROM news_facts").fetchone()[0] == s["facts"]
