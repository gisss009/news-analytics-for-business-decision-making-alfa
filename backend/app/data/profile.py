"""Профиль компании: список признаков, каждый со ссылкой на источник, уверенностью и флагом пропуска.

Ссылка на признак в выводах ИИ: `feat:<name>` (docs/ARCHITECTURE.md §5.3).
Запуск: python -m app.data.profile U_S0001
"""
import json
import sqlite3
import sys
from typing import Any

from pydantic import BaseModel

from app.core.db import session
from app.data.models import source_of
from app.data.okved import sector_of

LARGE_REVENUE_RUB = 15e9
REVENUE_PLACEHOLDER = 1000.0  # в датасете кейса так выглядит отсутствие данных о выручке

PRODUCT_FIELDS = {
    "has_rko": "расчётно-кассовое обслуживание",
    "has_guarantees": "банковские гарантии",
    "has_loans": "кредиты",
    "has_leasing": "лизинг",
    "has_deposits": "депозиты",
    "has_payroll": "зарплатный проект",
    "has_factoring": "факторинг",
}


class Feature(BaseModel):
    name: str
    value: Any
    title: str
    source: str
    confidence: float = 1.0
    missing: bool = False


class CompanyNotFound(LookupError):
    pass


def get_company(company_id: str, conn: sqlite3.Connection | None = None) -> dict:
    def q(c):
        row = c.execute("SELECT c.*, n.display_name FROM companies c LEFT JOIN company_names n USING (company_id) "
                        "WHERE c.company_id = ?", (company_id,)).fetchone()
        if row is None:
            raise CompanyNotFound(company_id)
        return dict(row)
    if conn is not None:
        return q(conn)
    with session() as c:
        return q(c)


def _field(row: dict, field: str, title: str, value: Any = None, confidence: float = 1.0) -> Feature:
    raw = row.get(field)
    missing = raw is None
    return Feature(name=field, value=raw if value is None else value, title=title, source=source_of(field),
                   confidence=0.0 if missing else confidence, missing=missing)


def build_profile(company_id: str) -> list[Feature]:
    with session() as conn:
        row = get_company(company_id, conn)
        group_size = conn.execute("SELECT COUNT(*) FROM companies WHERE group_id = ?",
                                  (row["group_id"],)).fetchone()[0] if row["group_id"] else 0
    feats: list[Feature] = []

    sector = sector_of(row["okved_code"])
    feats.append(Feature(name="sector", value=sector.name, title=f"Отрасль: {sector.title}",
                         source=f"{source_of('okved_code')} → okved_map.yaml", confidence=sector.confidence,
                         missing=row["okved_code"] is None))
    feats.append(_field(row, "okved_code", f"Основной ОКВЭД: {row['okved_name'] or 'нет данных'}"))

    rev = row["revenue"]
    rev_missing = rev is None or rev <= REVENUE_PLACEHOLDER
    feats.append(Feature(name="revenue_rub", value=rev, title="Выручка, руб.", source=source_of("revenue"),
                         confidence=0.0 if rev_missing else 0.9, missing=rev_missing))
    feats.append(Feature(name="large_company", value=(not rev_missing and rev >= LARGE_REVENUE_RUB),
                         title="Крупный бизнес (выручка от 15 млрд руб.)", source=source_of("revenue"),
                         confidence=0.2 if rev_missing else 0.9, missing=rev_missing))

    spark = row["workers_spark"]
    feats.append(_field(row, "workers_fns", "Численность по ФНС", confidence=0.9 if spark is None or spark == row["workers_fns"] else 0.7))
    feats.append(_field(row, "workers_spark", "Численность по СПАРК", confidence=0.8))
    feats.append(_field(row, "age_grade", "Возраст компании, лет"))
    feats.append(_field(row, "eco_stage", "Стадия развития", confidence=0.7))
    feats.append(_field(row, "okfs_name", "Форма собственности"))
    foreign = bool(row["okfs_name"]) and "ИНОСТРАН" in row["okfs_name"]
    feats.append(Feature(name="foreign_ownership", value=foreign, title="Иностранное участие в капитале",
                         source=source_of("okfs_name"), confidence=0.0 if row["okfs_name"] is None else 0.9,
                         missing=row["okfs_name"] is None))
    feats.append(_field(row, "cl_type", "Статус клиента банка"))

    for field, title in PRODUCT_FIELDS.items():
        f = _field(row, field, f"Продукт банка: {title}")
        f.value = bool(f.value) if not f.missing else None
        feats.append(f)

    fed = _field(row, "fts_flag", "ВЭД по данным ФТС")
    fed.value = bool(fed.value) if not fed.missing else None
    feats.append(fed)
    countries = [c.strip() for c in (row["fts_countries"] or "").split(",") if c.strip()]
    feats.append(Feature(name="fts_countries", value=countries, title="Страны ВЭД", source=source_of("fts_countries"),
                         confidence=0.9 if countries else (0.6 if fed.value is False else 0.3),
                         missing=not countries and bool(fed.value)))

    feats.append(_field(row, "region", "Регион"))
    feats.append(_field(row, "city", "Город"))
    feats.append(_field(row, "group_id", "Группа компаний"))
    feats.append(Feature(name="group_size", value=group_size, title="Компаний в группе (в данных банка)",
                         source=f"{source_of('group_id')} (подсчёт)", confidence=0.8,
                         missing=row["group_id"] is None))
    neg = _field(row, "negative_mark", "Негативная отметка")
    neg.value = bool(neg.value) if not neg.missing else None
    feats.append(neg)
    return feats


def profile_dict(company_id: str) -> dict[str, Feature]:
    return {f.name: f for f in build_profile(company_id)}


if __name__ == "__main__":
    for f in build_profile(sys.argv[1]):
        flag = " [ПРОПУСК]" if f.missing else ""
        print(f"{f.name:<18} {json.dumps(f.value, ensure_ascii=False):<40} conf={f.confidence:.2f}  {f.source}{flag}")
