from app.ingest.fixtures import TOPICS, load_fixtures, stats


def test_fixtures_valid_and_rich():
    items = load_fixtures(include_holdout=True)
    s = stats(items)
    assert s["total"] - s["holdout"] >= 40 and s["holdout"] >= 5
    assert len(s["topics"]) >= 9 and set(s["topics"]) <= set(TOPICS)
    assert s["duplicate_groups"] >= 4 and s["noise"] >= 3


def test_holdout_excluded_by_default():
    assert not any(i.holdout for i in load_fixtures())
    assert any(i.holdout for i in load_fixtures(include_holdout=True))


def test_injection_sample_present():
    assert any("Игнорируй" in i.text for i in load_fixtures())
