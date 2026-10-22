import pytest

from app.data.okved import FACTORS, MAP_PATH, all_sectors, load_map, sector_of


@pytest.mark.parametrize("code,sector", [
    ("46.71", "fuel_trade"), ("46.71.1", "fuel_trade"), ("46.51", "wholesale_trade"), ("46.46", "pharma_trade"),
    ("07.29.41", "gold_mining"), ("07.10", "mining_metals"), ("41.20", "construction"), ("06.10", "oil_gas"),
    ("47.71", "retail"), ("64.91", "finance_leasing"), ("01.11", "agriculture"), ("62.01", "it"),
])
def test_known_codes(code, sector):
    s = sector_of(code)
    assert s.name == sector and s.confidence >= 0.7 and set(s.factors) == set(FACTORS)


def test_longest_prefix_wins_and_confidence():
    assert sector_of("46.72").confidence > sector_of("46.51").confidence
    assert sector_of("46.2").name == "food_trade" and sector_of("46.21").name == "food_trade"
    assert sector_of("4").name == "other"  # "4" не совпадает с "46"


@pytest.mark.parametrize("code", ["99.99", "", None, "XX"])
def test_unknown_code_is_other_low_confidence(code):
    s = sector_of(code)
    assert s.name == "other" and s.confidence < 0.5


def test_new_sector_added_via_yaml_only(tmp_path):
    text = MAP_PATH.read_text(encoding="utf-8") + (
        "  space:\n    title: Космос\n    prefixes: [\"99.99\"]\n    factors: {fx: 0.9}\n    keywords: [космос]\n")
    p = tmp_path / "map.yaml"
    p.write_text(text, encoding="utf-8")
    s = sector_of("99.99", path=p)
    assert s.name == "space" and s.factors["fx"] == 0.9 and s.keywords == ("космос",)


def test_unknown_factor_rejected(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text(MAP_PATH.read_text(encoding="utf-8") + "  bad:\n    title: x\n    prefixes: []\n    factors: {moon: 1}\n",
                 encoding="utf-8")
    load_map.cache_clear()
    with pytest.raises(ValueError):
        sector_of("01", path=p)


def test_all_sectors_have_title():
    assert all(s.title for s in all_sectors())
