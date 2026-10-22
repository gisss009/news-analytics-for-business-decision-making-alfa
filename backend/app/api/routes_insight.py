"""Инсайт по событию для компании, прогресс шагов агента (SSE) и открытие первоисточника по ссылке."""
import json
import queue
import threading

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.cache import get_or_run
from app.agents.events import EventNotFound, get_event
from app.agents.schemas import LABEL_TITLES, Insight, TraceStep
from app.agents.tools import RefNotFound, resolve_ref
from app.api.main import ApiError
from app.api.routes_clients import require_company, require_role

router = APIRouter(tags=["insight"])

STEP_TITLES = {"planner": "Планирую, какие данные нужны", "retriever": "Собираю новости, аналитику и данные компании",
               "ranker": "Оцениваю значимость для компании", "bank_view": "Ищу позицию аналитиков банка",
               "interpreter": "Формирую интерпретацию", "verifier": "Проверяю источники и числа",
               "repair_search": "Ищу недостающие подтверждения"}


class InsightResponse(BaseModel):
    insight: Insight
    cached: bool
    label_titles: dict[str, str]


class StepEvent(BaseModel):
    step: str
    title: str
    status: str
    duration_ms: int


class RefView(BaseModel):
    ref: str
    kind: str
    title: str
    text: str
    quote: str | None = None
    url: str | None = None
    source: str | None = None
    date: str | None = None
    page: int | None = None
    excerpt_only: bool = False


def _check(event_id: str, client: str, role: str) -> None:
    require_company(client)
    require_role(role)
    try:
        get_event(event_id)
    except EventNotFound:
        raise ApiError(404, "event_not_found", f"Событие {event_id} не найдено")


@router.get("/events/{event_id}/insight", response_model=InsightResponse)
def insight(event_id: str, client: str = Query(...), role: str = "cfo") -> InsightResponse:
    """Шесть блоков интерпретации события для компании; повторный запрос берётся из кэша."""
    _check(event_id, client, role)
    ins, cached = get_or_run(client, event_id, role)
    return InsightResponse(insight=ins, cached=cached, label_titles=LABEL_TITLES)


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


@router.get("/events/{event_id}/insight/stream", response_class=StreamingResponse,
            responses={200: {"model": StepEvent, "content": {"text/event-stream": {}},
                             "description": "События step (StepEvent), затем done (InsightResponse) или error"}})
def insight_stream(event_id: str, client: str = Query(...), role: str = "cfo"):
    """Прогресс шагов агента для индикатора в интерфейсе (Server-Sent Events)."""
    _check(event_id, client, role)
    q: queue.Queue = queue.Queue()

    def on_step(ts: TraceStep) -> None:
        q.put(("step", StepEvent(step=ts.step, title=STEP_TITLES.get(ts.step, ts.step), status=ts.status,
                                 duration_ms=ts.duration_ms).model_dump_json()))

    def worker() -> None:
        try:
            ins, cached = get_or_run(client, event_id, role, on_step=on_step)
            q.put(("done", InsightResponse(insight=ins, cached=cached, label_titles=LABEL_TITLES).model_dump_json()))
        except Exception:  # noqa: BLE001 — клиенту уходит понятная ошибка, подробности в логе
            q.put(("error", json.dumps({"code": "insight_failed", "message": "Не удалось сформировать интерпретацию"},
                                       ensure_ascii=False)))

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            kind, data = q.get()
            yield _sse(kind, data)
            if kind in ("done", "error"):
                break

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.get("/refs", response_model=RefView)
def open_ref(ref: str = Query(..., examples=["news:n001#f1"]), client: str = Query(...)) -> RefView:
    """Первоисточник по ссылке из вывода: факт новости, страница аналитики, тезис, признак компании."""
    require_company(client)
    try:
        r = resolve_ref(ref, client)
    except RefNotFound as e:
        raise ApiError(404, "ref_not_found", str(e))
    return RefView(ref=ref, kind=r["kind"], title=str(r.get("title") or ref), text=str(r.get("text") or ""),
                   quote=r.get("quote"), url=r.get("url"), source=r.get("source"),
                   date=str(r["date"]) if r.get("date") else (str(r["published_at"]) if r.get("published_at") else None),
                   page=r.get("page"), excerpt_only=bool(r.get("excerpt_only", False)))
