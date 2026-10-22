"""Граф платежей: контрагенты, концентрация, связи внутри группы и с другими отраслями и регионами.

Ориентированный граф хранится в таблице payments (payer → beneficiary); запросы — SQL без networkx.
Платежи компании самой себе не учитываются. Контрагент может отсутствовать в таблице companies.
Ссылка на контрагента в выводах ИИ: `cp:<company_id>`.
"""
from typing import Literal

from app.core.db import session
from app.data.okved import sector_of

Direction = Literal["suppliers", "buyers"]

_SQL = {
    # поставщики: компания платит им (payer = company)
    "suppliers": "SELECT beneficiary AS cp, amount, pay_count FROM payments WHERE payer = ? AND beneficiary <> payer",
    # покупатели: платят компании (beneficiary = company)
    "buyers": "SELECT payer AS cp, amount, pay_count FROM payments WHERE beneficiary = ? AND beneficiary <> payer",
}


def _edges(conn, company_id: str, direction: Direction) -> list[dict]:
    rows = conn.execute(
        f"SELECT e.cp, e.amount, e.pay_count, c.okved_code, c.region, c.group_id, n.display_name "
        f"FROM ({_SQL[direction]}) e LEFT JOIN companies c ON c.company_id = e.cp "
        f"LEFT JOIN company_names n ON n.company_id = e.cp ORDER BY e.amount DESC, e.cp", (company_id,)).fetchall()
    return [dict(r) for r in rows]


def counterparties(company_id: str, direction: Direction, top: int = 5) -> list[dict]:
    """Топ контрагентов по объёму с долей в общем объёме направления."""
    with session() as conn:
        edges = _edges(conn, company_id, direction)
    total = sum(e["amount"] for e in edges) or 1.0
    out = []
    for e in edges[:top]:
        known = e["okved_code"] is not None
        out.append({"company_id": e["cp"], "name": e["display_name"], "in_dataset": known,
                    "sector": sector_of(e["okved_code"]).name if known else None, "region": e["region"],
                    "amount": e["amount"], "pay_count": e["pay_count"], "share": round(e["amount"] / total, 4),
                    "ref": f"cp:{e['cp']}"})
    return out


def concentration(company_id: str) -> dict:
    """Доля топ-3 контрагентов в объёме платежей по каждому направлению (0..1)."""
    out = {}
    with session() as conn:
        for d in ("suppliers", "buyers"):
            amounts = [e["amount"] for e in _edges(conn, company_id, d)]
            total = sum(amounts)
            out[f"{d}_count"] = len(amounts)
            out[f"{d}_top3_share"] = round(sum(amounts[:3]) / total, 4) if total else 0.0
            out[f"{d}_volume"] = total
    return out


def group_links(company_id: str) -> dict:
    """Компании той же группы и объём платежей с ними."""
    with session() as conn:
        row = conn.execute("SELECT group_id FROM companies WHERE company_id = ?", (company_id,)).fetchone()
        if row is None or row["group_id"] is None:
            return {"group_id": None, "members": [], "intra_group_volume": 0.0, "intra_group_share": 0.0}
        members = [r["company_id"] for r in conn.execute(
            "SELECT company_id FROM companies WHERE group_id = ? AND company_id <> ? ORDER BY company_id",
            (row["group_id"], company_id))]
        edges = _edges(conn, company_id, "suppliers") + _edges(conn, company_id, "buyers")
    total = sum(e["amount"] for e in edges)
    intra = sum(e["amount"] for e in edges if e["cp"] in set(members))
    return {"group_id": row["group_id"], "members": members, "intra_group_volume": intra,
            "intra_group_share": round(intra / total, 4) if total else 0.0}


def cross_links(company_id: str) -> dict:
    """Доли объёма с контрагентами из других отраслей и регионов (по известным контрагентам)."""
    with session() as conn:
        me = conn.execute("SELECT okved_code, region FROM companies WHERE company_id = ?", (company_id,)).fetchone()
        edges = _edges(conn, company_id, "suppliers") + _edges(conn, company_id, "buyers")
    if me is None:
        return {"known_volume": 0.0, "other_sector_share": 0.0, "other_region_share": 0.0, "other_sectors": []}
    my_sector = sector_of(me["okved_code"]).name
    known = [e for e in edges if e["okved_code"] is not None]
    total = sum(e["amount"] for e in known)
    other_sector = [e for e in known if sector_of(e["okved_code"]).name != my_sector]
    other_region = [e for e in known if e["region"] != me["region"]]
    return {
        "known_volume": total,
        "other_sector_share": round(sum(e["amount"] for e in other_sector) / total, 4) if total else 0.0,
        "other_region_share": round(sum(e["amount"] for e in other_region) / total, 4) if total else 0.0,
        "other_sectors": sorted({sector_of(e["okved_code"]).name for e in other_sector}),
    }
