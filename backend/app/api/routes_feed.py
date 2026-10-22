"""Персонализированная лента событий для клиента."""
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.agents.ranker import rank_events
from app.api.routes_clients import require_company, require_role

router = APIRouter(tags=["feed"])

TOPIC_TITLES = {"rate": "Ставка", "fx": "Курс", "commodities": "Сырьё", "inflation": "Инфляция",
                "regulation": "Регулирование", "taxes": "Налоги", "sanctions_trade": "Санкции и ВЭД",
                "industry": "Отрасли", "capital_markets": "Рынок капитала", "other": "Прочее"}


class FeedEvent(BaseModel):
    event_id: str
    title: str
    topic: str
    topic_title: str
    first_seen: datetime
    score: float
    reasons: list[str]
    matched_features: list[str]
    sources: list[str]
    annotation: str
    sectors: list[str]


class Feed(BaseModel):
    client_id: str
    role: str
    generated_at: datetime
    topics: dict[str, str]
    events: list[FeedEvent]


def build_feed(client_id: str, role: str, topic: str | None, limit: int) -> Feed:
    require_company(client_id)
    require_role(role)
    events = rank_events(client_id, role=role, topic=topic, limit=limit)
    return Feed(client_id=client_id, role=role, generated_at=datetime.now(timezone.utc), topics=TOPIC_TITLES,
                events=[FeedEvent(**{k: e[k] for k in FeedEvent.model_fields if k in e},
                                  topic_title=TOPIC_TITLES.get(e["topic"], e["topic"])) for e in events])


@router.get("/clients/{client_id}/feed", response_model=Feed)
def feed(client_id: str, role: str = "cfo", topic: str | None = Query(default=None),
         limit: int = Query(default=12, ge=1, le=50)) -> Feed:
    """События, отсортированные по значимости для компании; у каждого — причины «почему в вашей ленте»."""
    return build_feed(client_id, role, topic, limit)


class RefreshResult(BaseModel):
    status: str
    events: int


@router.post("/clients/{client_id}/feed/refresh", response_model=RefreshResult)
def refresh(client_id: str, role: str = "cfo") -> RefreshResult:
    """Пересчёт ленты (в прототипе лента считается на лету, кэша ленты нет)."""
    return RefreshResult(status="ok", events=len(build_feed(client_id, role, None, 50).events))
