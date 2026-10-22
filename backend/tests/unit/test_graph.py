import pytest

from app.core.db import session
from app.data.graph import concentration, counterparties, cross_links, group_links


@pytest.fixture
def small_graph():
    """A платит B (60), C (30), D (10), себе (500); E платит A (40). A, B в одной группе. D вне выборки."""
    with session() as conn:
        conn.executemany(
            "INSERT INTO companies (company_id, okved_code, region, group_id, dataset) VALUES (?, ?, ?, ?, 't')",
            [("A", "41.20", "Москва", "g1"), ("B", "41.20", "Москва", "g1"), ("C", "46.72", "Казань", "g2"),
             ("E", "62.01", "Москва", "g3"), ("Z", "47.11", "Москва", None)])
        conn.executemany("INSERT INTO payments (beneficiary, payer, amount, pay_count) VALUES (?, ?, ?, ?)",
                         [("B", "A", 60, 6), ("C", "A", 30, 3), ("D", "A", 10, 1), ("A", "A", 500, 1),
                          ("A", "E", 40, 2)])


def test_top_suppliers_and_buyers(small_graph):
    sup = counterparties("A", "suppliers", top=2)
    assert [s["company_id"] for s in sup] == ["B", "C"]
    assert sup[0]["share"] == 0.6 and sup[0]["ref"] == "cp:B" and sup[1]["sector"] == "metals_trade"
    assert [b["company_id"] for b in counterparties("A", "buyers")] == ["E"]
    d = counterparties("A", "suppliers", top=5)[-1]
    assert d["company_id"] == "D" and d["in_dataset"] is False and d["sector"] is None


def test_concentration_ignores_self_payments(small_graph):
    c = concentration("A")
    assert c["suppliers_top3_share"] == 1.0 and c["suppliers_count"] == 3 and c["suppliers_volume"] == 100
    assert c["buyers_top3_share"] == 1.0


def test_group_and_cross_links(small_graph):
    g = group_links("A")
    assert g["members"] == ["B"] and g["intra_group_volume"] == 60 and g["intra_group_share"] == pytest.approx(60 / 140, abs=1e-4)
    x = cross_links("A")
    assert x["known_volume"] == 130  # D вне выборки не учитывается
    assert x["other_sector_share"] == pytest.approx(70 / 130, abs=1e-4)
    assert x["other_region_share"] == pytest.approx(30 / 130, abs=1e-4)
    assert x["other_sectors"] == ["it", "metals_trade"]


def test_company_without_payments_returns_empty(small_graph):
    assert counterparties("Z", "suppliers") == []
    assert concentration("Z")["suppliers_top3_share"] == 0.0
    assert group_links("Z")["members"] == []
    assert cross_links("NOPE")["known_volume"] == 0.0
