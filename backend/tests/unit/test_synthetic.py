import hashlib

from app.core.db import connect
from app.data.loader import load_all
from app.data.synthetic import ANCHORS, generate, stats


def digest(paths):
    return {name: hashlib.sha256(p.read_bytes()).hexdigest() for name, p in paths.items()}


def test_same_seed_same_files(tmp_path):
    a = digest(generate(42, tmp_path / "a"))
    b = digest(generate(42, tmp_path / "b"))
    c = digest(generate(7, tmp_path / "c"))
    assert a == b and a != c


def test_distribution_not_degenerate(tmp_path):
    generate(42, tmp_path)
    s = stats(tmp_path)
    assert s["big_companies"] >= 30
    assert s["big_okved_groups"] >= 8 and len(s["big_sectors"]) >= 8
    assert s["big_regions"] >= 5
    for col in ("CL_PRODUCT_LOA_MARK", "CL_PRODUCT_LEA_MARK", "CL_PRODUCT_GAR_MARK", "FTS_FLAG"):
        assert 0 < s["big_products"][col] < s["big_companies"], col
    assert s["groups_with_2plus"] >= 3 and s["payments"] > 200 and s["persons"] >= 100


def test_loader_accepts_synthetic(tmp_path):
    generate(42, tmp_path)
    st = load_all(tmp_path, "synthetic")
    assert st["duplicate_company_ids"] == 0
    conn = connect()
    anchor = conn.execute("SELECT * FROM companies WHERE company_id = 'U_S0001'").fetchone()
    assert anchor["okved_code"] == ANCHORS[0][1] and anchor["has_loans"] == 1 and anchor["revenue"] >= 15e9
    gold = conn.execute("SELECT has_loans, fts_countries FROM companies WHERE company_id = 'U_S0002'").fetchone()
    assert gold["has_loans"] == 0 and "КИТАЙ" in gold["fts_countries"]
    assert conn.execute("SELECT COUNT(*) FROM companies WHERE company_id NOT LIKE 'U_S%'").fetchone()[0] == 0
    name = conn.execute("SELECT display_name FROM company_names WHERE company_id = 'U_S0001'").fetchone()[0]
    assert name.endswith("(синтетика)")
