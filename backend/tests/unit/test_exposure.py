import pytest

from app.core.db import session
from app.data.exposure import exposure_dict, exposures
from app.data.loader import load_all
from app.data.synthetic import generate

NAMES = {"rate_sensitivity", "fx_exposure", "commodity_links", "supply_concentration", "region_risk",
         "group_dependency", "inflation_sensitivity", "demand_sensitivity", "sanctions_exposure",
         "regulation_sensitivity"}


@pytest.fixture
def synthetic(tmp_path):
    generate(42, tmp_path)
    load_all(tmp_path, "synthetic")


def test_all_exposures_valid(synthetic):
    for uid in ("U_S0001", "U_S0002", "U_S0004", "U_S0005"):
        ex = exposures(uid)
        assert {e.name for e in ex} == NAMES
        for e in ex:
            assert 0 <= e.score <= 1 and e.explanation and e.based_on and e.refs, (uid, e.name)


def test_loans_raise_rate_sensitivity(synthetic):
    with session() as conn:
        conn.execute("UPDATE companies SET has_loans = 1, has_leasing = 1 WHERE company_id = 'U_S0002'")
    with_loans = exposure_dict("U_S0002")["rate_sensitivity"].score
    with session() as conn:
        conn.execute("UPDATE companies SET has_loans = 0, has_leasing = 0 WHERE company_id = 'U_S0002'")
    without = exposure_dict("U_S0002")["rate_sensitivity"].score
    assert with_loans > without
    assert "feat:has_loans" in exposure_dict("U_S0001")["rate_sensitivity"].refs


def test_sector_specific_exposures(synthetic):
    gold, builder, importer = exposure_dict("U_S0002"), exposure_dict("U_S0001"), exposure_dict("U_S0004")
    assert gold["commodity_links"].details["by_commodity"]["gold"] >= 0.9
    assert builder["rate_sensitivity"].score > gold["rate_sensitivity"].score
    assert importer["fx_exposure"].score > builder["fx_exposure"].score
    assert importer["supply_concentration"].score > 0.3  # у U_S0004 подсажен крупный поставщик
    assert any(r.startswith("cp:") for r in importer["supply_concentration"].refs)


def test_company_without_payments(synthetic):
    with session() as conn:
        conn.execute("DELETE FROM payments WHERE payer = 'U_S0005' OR beneficiary = 'U_S0005'")
    e = exposure_dict("U_S0005")
    assert e["supply_concentration"].score == 0 and "нет" in e["supply_concentration"].explanation
