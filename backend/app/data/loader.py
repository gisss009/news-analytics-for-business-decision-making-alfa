"""Загрузка CSV кейса (data/raw) или синтетики (data/synthetic) в SQLite.

Загрузка идемпотентна: таблицы данных полностью заменяются в одной транзакции.
Запуск: python -m app.data.loader [--source synthetic|raw]
"""
import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.core.db import session
from app.core.logging import get_logger
from app.data.models import (COMPANIES_FILE, COMPANY_COLUMNS, CSV_DELIMITER, PAYMENT_COLUMNS, PAYMENTS_FILE,
                             PERSON_COLUMNS, PERSONS_FILE)

log = get_logger("data.loader")


def _convert(value: str, kind: str):
    value = value.strip()
    if value == "":
        return None
    if kind == "flag":
        return int(float(value))
    if kind == "float":
        return float(value)
    return value


def read_rows(path: Path, spec: dict[str, tuple[str, str]]):
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=CSV_DELIMITER)
        missing = set(spec) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name}: нет столбцов {sorted(missing)}")
        for row in reader:
            yield {name: _convert(row[col], kind) for col, (name, kind) in spec.items()}


def load_all(source_dir: Path | str, dataset: str | None = None) -> dict:
    """Загружает три файла из source_dir. Возвращает статистику загрузки."""
    source_dir = Path(source_dir)
    dataset = dataset or source_dir.name
    stats = {"dataset": dataset, "companies": 0, "duplicate_company_ids": 0, "persons": 0,
             "payments": 0, "payment_pairs_merged": 0}

    companies: dict[str, dict] = {}
    for row in read_rows(source_dir / COMPANIES_FILE, COMPANY_COLUMNS):
        if row["company_id"] in companies:
            stats["duplicate_company_ids"] += 1  # оставляем первую строку (см. docs/data-dictionary.md)
            continue
        companies[row["company_id"]] = row

    payments: dict[tuple[str, str], dict] = {}
    for row in read_rows(source_dir / PAYMENTS_FILE, PAYMENT_COLUMNS):
        key = (row["beneficiary"], row["payer"])
        if key in payments:
            payments[key]["amount"] += row["amount"]
            payments[key]["pay_count"] += row["pay_count"]
            stats["payment_pairs_merged"] += 1
        else:
            payments[key] = row

    persons = {(r["person_id"], r["company_id"]): r for r in read_rows(source_dir / PERSONS_FILE, PERSON_COLUMNS)}

    company_fields = [name for name, _ in COMPANY_COLUMNS.values()] + ["dataset"]
    with session() as conn:
        conn.execute("DELETE FROM companies")
        conn.execute("DELETE FROM persons")
        conn.execute("DELETE FROM payments")
        conn.executemany(
            f"INSERT INTO companies ({', '.join(company_fields)}) VALUES ({', '.join('?' * len(company_fields))})",
            ([*c.values(), dataset] for c in companies.values()))
        conn.executemany("INSERT INTO persons (person_id, company_id, city_name, rc_name) VALUES (?, ?, ?, ?)",
                         ((p["person_id"], p["company_id"], p["city_name"], p["rc_name"]) for p in persons.values()))
        conn.executemany("INSERT INTO payments (beneficiary, payer, amount, pay_count) VALUES (?, ?, ?, ?)",
                         ((p["beneficiary"], p["payer"], p["amount"], int(p["pay_count"])) for p in payments.values()))
        conn.execute("INSERT OR REPLACE INTO data_meta (key, value) VALUES ('dataset', ?), ('loaded_at', ?)",
                     (dataset, datetime.now(timezone.utc).isoformat()))
    stats.update(companies=len(companies), persons=len(persons), payments=len(payments))
    if stats["duplicate_company_ids"]:
        log.warning("duplicate_company_ids", extra={"count": stats["duplicate_company_ids"]})
    return stats


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", choices=["synthetic", "raw"], default="synthetic")
    a = p.parse_args()
    print(load_all(settings.data_dir / a.source, a.source))


if __name__ == "__main__":
    main()
