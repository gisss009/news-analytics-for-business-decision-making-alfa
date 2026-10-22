"""Таблицы companies, persons, payments и соответствие их полей столбцам CSV кейса (docs/data-dictionary.md).

Соответствие нужно профилю: каждый признак ссылается на исходный столбец, например
`df_Uid_data_hack.csv:CL_PRODUCT_LOA_MARK`.
"""
from app.core.db import register_schema

COMPANIES_FILE = "df_Uid_data_hack.csv"
PERSONS_FILE = "df_Fid_Uid_link_hack.csv"
PAYMENTS_FILE = "df_Uid_payment_hack.csv"
NAMES_FILE = "synthetic_company_names.csv"  # только у синтетики: отображаемые названия
CSV_DELIMITER = ";"

# столбец CSV → (поле таблицы, тип: str | flag | float)
COMPANY_COLUMNS: dict[str, tuple[str, str]] = {
    "SYNTHETIC_U": ("company_id", "str"),
    "ORG_TYPE": ("org_type", "str"),
    "OKFS_NAME": ("okfs_name", "str"),
    "COMPANY_AGE_YEARS_GRADATION": ("age_grade", "str"),
    "ECO_MARK_LABEL": ("eco_stage", "str"),
    "MAINOKVED_CODE": ("okved_code", "str"),
    "MAINOKVED_NAME": ("okved_name", "str"),
    "NEGATIVEMARK": ("negative_mark", "flag"),
    "AMOUNT_WORKERS_FNS_GRADATION": ("workers_fns", "str"),
    "AMOUNT_WORKERS_SPARK_GRADATION": ("workers_spark", "str"),
    "CL_TYPE": ("cl_type", "str"),
    "CL_PRODUCT_RKO_MARK": ("has_rko", "flag"),
    "CL_PRODUCT_GAR_MARK": ("has_guarantees", "flag"),
    "CL_PRODUCT_LOA_MARK": ("has_loans", "flag"),
    "CL_PRODUCT_LEA_MARK": ("has_leasing", "flag"),
    "CL_PRODUCT_DEP_MARK": ("has_deposits", "flag"),
    "CL_PRODUCT_ZPP_MARK": ("has_payroll", "flag"),
    "FTS_FLAG": ("fts_flag", "flag"),
    "FTS_COUNTRY_NAME": ("fts_countries", "str"),
    "FACTORING_MARK": ("has_factoring", "flag"),
    "REVENUE_COMPANY": ("revenue", "float"),
    "GROUP_ID": ("group_id", "str"),
    "CITY": ("city", "str"),
    "REGION": ("region", "str"),
}
PERSON_COLUMNS: dict[str, tuple[str, str]] = {
    "SYNTHETIC_F": ("person_id", "str"),
    "CITY_NAME": ("city_name", "str"),
    "RC_NAME": ("rc_name", "str"),
    "SYNTHETIC_U": ("company_id", "str"),
}
PAYMENT_COLUMNS: dict[str, tuple[str, str]] = {
    "BENEFICIARY": ("beneficiary", "str"),
    "PAYER": ("payer", "str"),
    "PAY_AMT": ("amount", "float"),
    "PAY_CNT": ("pay_count", "float"),
}

_SQL_TYPE = {"str": "TEXT", "flag": "INTEGER", "float": "REAL"}


def source_of(field: str) -> str:
    """Ссылка на исходный столбец для поля таблицы companies: 'df_Uid_data_hack.csv:<COLUMN>'."""
    for col, (name, _) in COMPANY_COLUMNS.items():
        if name == field:
            return f"{COMPANIES_FILE}:{col}"
    raise KeyError(field)


def _columns(spec: dict[str, tuple[str, str]], skip: set[str]) -> str:
    return ",\n    ".join(f"{name} {_SQL_TYPE[t]}" for name, t in spec.values() if name not in skip)


register_schema("data_tables", f"""
CREATE TABLE IF NOT EXISTS companies (
    company_id TEXT PRIMARY KEY,
    {_columns(COMPANY_COLUMNS, {"company_id"})},
    dataset TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_companies_group ON companies(group_id);
CREATE INDEX IF NOT EXISTS ix_companies_okved ON companies(okved_code);

CREATE TABLE IF NOT EXISTS persons (
    person_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    city_name TEXT,
    rc_name TEXT,
    PRIMARY KEY (person_id, company_id)
);
CREATE INDEX IF NOT EXISTS ix_persons_company ON persons(company_id);

CREATE TABLE IF NOT EXISTS payments (
    beneficiary TEXT NOT NULL,
    payer TEXT NOT NULL,
    amount REAL NOT NULL,
    pay_count INTEGER NOT NULL,
    PRIMARY KEY (beneficiary, payer)
);
CREATE INDEX IF NOT EXISTS ix_payments_payer ON payments(payer);

CREATE TABLE IF NOT EXISTS company_names (
    company_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS data_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
""")
