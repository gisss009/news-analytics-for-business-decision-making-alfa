import pytest

from app.core.db import session
from app.data.loader import load_all
from app.data.profile import CompanyNotFound, build_profile, profile_dict
from app.data.synthetic import generate


@pytest.fixture
def synthetic(tmp_path):
    generate(42, tmp_path)
    load_all(tmp_path, "synthetic")


@pytest.mark.parametrize("uid,sector", [("U_S0001", "construction"), ("U_S0002", "gold_mining"),
                                        ("U_S0005", "it")])
def test_profiles_for_three_companies(synthetic, uid, sector):
    feats = build_profile(uid)
    assert all(f.source for f in feats)
    assert len({f.name for f in feats}) == len(feats)
    p = profile_dict(uid)
    assert p["sector"].value == sector and p["large_company"].value is True
    assert p["has_loans"].source == "df_Uid_data_hack.csv:CL_PRODUCT_LOA_MARK"


def test_known_facts(synthetic):
    p = profile_dict("U_S0001")
    assert p["has_loans"].value is True and p["has_leasing"].value is True and p["region"].value == "Москва"
    g = profile_dict("U_S0002")
    assert g["has_loans"].value is False and g["fts_flag"].value is True and "КИТАЙ" in g["fts_countries"].value


def test_missing_fields_are_marked_not_errors(synthetic):
    with session() as conn:
        conn.execute("UPDATE companies SET eco_stage = NULL, workers_spark = NULL, okfs_name = NULL, revenue = 1000, "
                     "has_loans = NULL, fts_flag = 1, fts_countries = NULL WHERE company_id = 'U_S0003'")
    p = profile_dict("U_S0003")
    for name in ("eco_stage", "workers_spark", "okfs_name", "revenue_rub", "has_loans", "fts_countries"):
        assert p[name].missing and p[name].confidence <= 0.3, name
    assert p["has_loans"].value is None and p["large_company"].missing
    assert not p["region"].missing


def test_unknown_company(synthetic):
    with pytest.raises(CompanyNotFound):
        build_profile("U_NOPE")
