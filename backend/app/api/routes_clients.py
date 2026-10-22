"""Клиенты (синтетические компании), роли ЛПР и профиль компании.

В прототипе нет входа (api.auth вне объёма): клиент выбирается явно, данные чужой компании внутри
агентного ядра всё равно недоступны (проверка в agents/tools.py).
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.api.main import ApiError
from app.core.db import session
from app.data.exposure import Exposure, exposures
from app.data.okved import sector_of
from app.data.profile import PRODUCT_FIELDS, CompanyNotFound, Feature, build_profile, get_company

router = APIRouter(tags=["clients"])

ROLES = {"ceo": "Собственник / генеральный директор", "cfo": "Финансовый директор",
         "treasurer": "Руководитель казначейства", "accountant": "Главный бухгалтер"}


class Role(BaseModel):
    id: str
    title: str


class ClientSummary(BaseModel):
    id: str
    name: str
    sector: str
    sector_title: str
    region: str | None
    revenue_rub: float | None
    products: list[str]
    fts_countries: list[str]


class Profile(BaseModel):
    client: ClientSummary
    features: list[Feature]
    exposures: list[Exposure]


def _summary(row: dict) -> ClientSummary:
    s = sector_of(row["okved_code"])
    return ClientSummary(
        id=row["company_id"], name=(row.get("display_name") or row["company_id"]).replace(" (синтетика)", ""),
        sector=s.name, sector_title=s.title, region=row["region"], revenue_rub=row["revenue"],
        products=[title for f, title in PRODUCT_FIELDS.items() if row.get(f) == 1],
        fts_countries=[c.strip() for c in (row["fts_countries"] or "").split(",") if c.strip()])


def require_company(company_id: str) -> dict:
    try:
        return get_company(company_id)
    except CompanyNotFound:
        raise ApiError(404, "client_not_found", f"Клиент {company_id} не найден")


def require_role(role: str) -> str:
    if role not in ROLES:
        raise ApiError(422, "invalid_role", f"Неизвестная роль {role}. Допустимо: {', '.join(ROLES)}")
    return role


@router.get("/roles", response_model=list[Role])
def roles() -> list[Role]:
    return [Role(id=k, title=v) for k, v in ROLES.items()]


@router.get("/clients", response_model=list[ClientSummary])
def clients() -> list[ClientSummary]:
    """Крупные компании (выручка от 15 млрд руб.) — целевой сегмент кейса."""
    with session() as conn:
        rows = conn.execute("SELECT c.*, n.display_name FROM companies c LEFT JOIN company_names n USING (company_id) "
                            "WHERE c.revenue >= 15e9 ORDER BY c.company_id").fetchall()
    return [_summary(dict(r)) for r in rows]


@router.get("/clients/{client_id}/profile", response_model=Profile)
def profile(client_id: str) -> Profile:
    row = require_company(client_id)
    return Profile(client=_summary(row), features=build_profile(client_id), exposures=exposures(client_id))
