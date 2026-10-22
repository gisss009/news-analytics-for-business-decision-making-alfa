from app.core.db import connect
from app.data.loader import load_all
from app.data.models import COMPANY_COLUMNS, source_of

HEADER = ";".join(COMPANY_COLUMNS)


def company(uid: str, revenue: str = "20000000000.0", loans: str = "1.0", spark: str = "") -> str:
    vals = {c: "" for c in COMPANY_COLUMNS}
    vals.update(SYNTHETIC_U=uid, ORG_TYPE="КОММ_ОРГ", MAINOKVED_CODE="46.71", MAINOKVED_NAME="Торговля оптовая топливом",
                CL_PRODUCT_LOA_MARK=loans, REVENUE_COMPANY=revenue, GROUP_ID="group_1_sb", REGION="Москва",
                AMOUNT_WORKERS_SPARK_GRADATION=spark, NEGATIVEMARK="0.0")
    return ";".join(vals.values())


def write_mini(d):
    (d / "df_Uid_data_hack.csv").write_text(
        "\n".join([HEADER, company("U_1"), company("U_2", loans="0.0"), company("U_1", revenue="5.0")]) + "\n",
        encoding="utf-8")
    (d / "df_Fid_Uid_link_hack.csv").write_text(
        'SYNTHETIC_F;CITY_NAME;RC_NAME;SYNTHETIC_U\nF_1;"Мск ""Юг""";МОСКОВСКИЙ;U_1\nF_1;Омск;;U_2\n', encoding="utf-8")
    (d / "df_Uid_payment_hack.csv").write_text(
        "BENEFICIARY;PAYER;PAY_AMT;PAY_CNT\nU_1;U_2;1000.0;2\nU_1;U_2;500.0;1\nU_2;U_9;7000.0;3\n", encoding="utf-8")


def test_load_types_duplicates_and_idempotency(tmp_path):
    write_mini(tmp_path)
    s1 = load_all(tmp_path, "synthetic")
    s2 = load_all(tmp_path, "synthetic")
    assert s1 == s2
    assert s1["companies"] == 2 and s1["duplicate_company_ids"] == 1 and s1["payment_pairs_merged"] == 1
    conn = connect()
    assert conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 2
    u1 = conn.execute("SELECT * FROM companies WHERE company_id = 'U_1'").fetchone()
    assert u1["revenue"] == 2e10 and u1["has_loans"] == 1 and u1["workers_spark"] is None
    pay = conn.execute("SELECT amount, pay_count FROM payments WHERE beneficiary='U_1' AND payer='U_2'").fetchone()
    assert (pay["amount"], pay["pay_count"]) == (1500.0, 3)
    assert conn.execute("SELECT city_name FROM persons WHERE company_id='U_1'").fetchone()[0] == 'Мск "Юг"'


def test_indexes_created():
    names = {r[0] for r in connect().execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert {"ix_companies_group", "ix_persons_company", "ix_payments_payer"} <= names


def test_source_of_field():
    assert source_of("has_loans") == "df_Uid_data_hack.csv:CL_PRODUCT_LOA_MARK"
