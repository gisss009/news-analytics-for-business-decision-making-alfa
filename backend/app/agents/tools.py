"""Реестр инструментов агентного ядра с контролем прав. Все инструменты только читают.

Правила:
- у каждого шага свой белый список инструментов (STEP_TOOLS); вызов вне списка → ToolNotAllowed;
- запуск привязан к компании пользователя: данные другой компании недоступны → AccessDenied;
- аргументы проверяются схемой; каждый вызов (успешный и отклонённый) пишется в tool_calls.
resolve_ref() открывает любую ссылку из выводов: news:*, news:*#f*, doc:*#p*, thesis:*, feat:*, exp:*, cp:*.
"""
from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic import BaseModel, ValidationError

from app.agents.schemas import ref_kind
from app.core.db import session
from app.core.logging import log_tool_call
from app.data import graph
from app.data.exposure import exposure_dict, exposures
from app.data.profile import CompanyNotFound, build_profile, get_company, profile_dict
from app.ingest import index
from app.ingest.index import Filters

READ_TOOLS = {"profile_get", "news_search", "analytics_search", "graph_query", "source_open"}
STEP_TOOLS: dict[str, set[str]] = {
    "planner": {"profile_get"},
    "retriever": READ_TOOLS,
    "ranker": {"profile_get"},
    "bank_view": {"analytics_search", "source_open"},
    "interpreter": set(),
    "verifier": {"source_open"},
    "followup": READ_TOOLS,
}


class ToolNotAllowed(PermissionError):
    pass


class AccessDenied(PermissionError):
    pass


class RefNotFound(LookupError):
    pass


@dataclass(frozen=True)
class ToolContext:
    company_id: str
    step: str
    run_id: str | None = None


# --- аргументы инструментов ---
class ProfileArgs(BaseModel):
    company_id: str


class SearchArgs(BaseModel):
    query: str
    filters: Filters = Filters()
    k: int = 5


class GraphArgs(BaseModel):
    company_id: str
    kind: Literal["suppliers", "buyers", "concentration", "group", "cross"]
    top: int = 5


class SourceArgs(BaseModel):
    ref: str


# --- реализация ---
def _check_company(ctx: ToolContext, company_id: str) -> None:
    if company_id != ctx.company_id:
        raise AccessDenied(f"шаг {ctx.step}: нет доступа к данным компании {company_id}")


def _profile_get(ctx: ToolContext, a: ProfileArgs) -> dict:
    _check_company(ctx, a.company_id)
    c = get_company(a.company_id)
    return {"company_id": a.company_id, "name": c["display_name"] or a.company_id,
            "features": [f.model_dump() for f in build_profile(a.company_id)],
            "exposures": [e.model_dump() for e in exposures(a.company_id)]}


def _news_search(ctx: ToolContext, a: SearchArgs) -> list[dict]:
    return [h.model_dump() for h in index.search(a.query, "news", a.filters, min(a.k, 20))]


def _analytics_search(ctx: ToolContext, a: SearchArgs) -> list[dict]:
    return [h.model_dump() for h in index.search(a.query, "analytics", a.filters, min(a.k, 20))]


def _graph_query(ctx: ToolContext, a: GraphArgs) -> Any:
    _check_company(ctx, a.company_id)
    if a.kind in ("suppliers", "buyers"):
        return graph.counterparties(a.company_id, a.kind, min(a.top, 20))
    return {"concentration": graph.concentration, "group": graph.group_links, "cross": graph.cross_links}[a.kind](a.company_id)


def _source_open(ctx: ToolContext, a: SourceArgs) -> dict:
    return resolve_ref(a.ref, ctx.company_id)


TOOLS: dict[str, tuple[type[BaseModel], Callable]] = {
    "profile_get": (ProfileArgs, _profile_get),
    "news_search": (SearchArgs, _news_search),
    "analytics_search": (SearchArgs, _analytics_search),
    "graph_query": (GraphArgs, _graph_query),
    "source_open": (SourceArgs, _source_open),
}


def call_tool(ctx: ToolContext, name: str, **args) -> Any:
    """Единственная точка вызова инструментов из шагов агентного ядра."""
    try:
        if name not in TOOLS:
            raise ToolNotAllowed(f"неизвестный инструмент {name}")
        if name not in STEP_TOOLS.get(ctx.step, set()):
            raise ToolNotAllowed(f"шагу {ctx.step} не разрешён инструмент {name}")
        schema, fn = TOOLS[name]
        parsed = schema(**args)
        result = fn(ctx, parsed)
    except (ToolNotAllowed, AccessDenied, ValidationError, RefNotFound, CompanyNotFound) as e:
        log_tool_call(ctx.step, name, args, result=str(e), ok=False)
        raise
    log_tool_call(ctx.step, name, args, result=result)
    return result


# --- открытие ссылок ---
def resolve_ref(ref: str, company_id: str) -> dict:
    """Текст и метаданные по ссылке. Для feat/exp/cp — только в рамках компании company_id."""
    kind = ref_kind(ref)
    if kind is None:
        raise RefNotFound(f"неизвестный формат ссылки {ref}")
    body = ref.split(":", 1)[1]
    with session() as conn:
        if kind == "news":
            r = conn.execute("SELECT * FROM news_items WHERE item_id = ?", (body,)).fetchone()
            if r:
                return {"ref": ref, "kind": "news", "title": r["title"], "text": r["text"], "url": r["url"],
                        "source": r["source_name"], "published_at": r["published_at"]}
        elif kind == "news_fact":
            r = conn.execute("SELECT f.*, n.title, n.url, n.source_name FROM news_facts f JOIN news_items n USING (item_id) "
                             "WHERE f.fact_id = ?", (ref,)).fetchone()
            if r:
                return {"ref": ref, "kind": "fact", "title": r["title"], "text": r["quote"], "quote": r["quote"],
                        "url": r["url"], "source": r["source_name"], "date": r["date"], "modality": r["modality"]}
        elif kind == "doc":
            doc_id, page = body.split("#p")
            r = conn.execute("SELECT p.text, d.title, d.date, d.file, d.stale FROM analytics_pages p "
                             "JOIN analytics_docs d USING (doc_id) WHERE p.doc_id = ? AND p.page = ?",
                             (doc_id, int(page))).fetchone()
            if r:
                return {"ref": ref, "kind": "doc", "title": r["title"], "text": r["text"], "page": int(page),
                        "date": r["date"], "file": r["file"], "stale": bool(r["stale"]), "excerpt_only": True}
        elif kind == "thesis":
            r = conn.execute("SELECT t.*, d.title AS doc_title, d.date FROM theses t JOIN analytics_docs d USING (doc_id) "
                             "WHERE t.thesis_id = ?", (body,)).fetchone()
            if r:
                return {"ref": ref, "kind": "thesis", "title": r["doc_title"], "text": r["text"], "quote": r["quote"],
                        "page": r["page"], "doc_ref": f"doc:{r['doc_id']}#p{r['page']}", "date": r["date"]}
    if kind == "feat":
        f = profile_dict(company_id).get(body)
        if f:
            return {"ref": ref, "kind": "feature", "title": f.title, "text": f"{f.title}: {f.value}", "value": f.value,
                    "source": f.source, "missing": f.missing, "confidence": f.confidence}
    elif kind == "exp":
        e = exposure_dict(company_id).get(body)
        if e:
            return {"ref": ref, "kind": "exposure", "title": e.name, "text": e.explanation, "score": e.score,
                    "based_on": e.based_on}
    elif kind == "cp":
        cps = graph.counterparties(company_id, "suppliers", 100) + graph.counterparties(company_id, "buyers", 100)
        group = graph.group_links(company_id)["members"]
        hit = next((c for c in cps if c["company_id"] == body), None)
        if hit:
            return {"ref": ref, "kind": "counterparty", "title": hit["name"] or body,
                    "text": f"Контрагент: {hit['name'] or body}, отрасль {hit['sector'] or 'нет данных'}, "
                            f"доля в платежах {hit['share']:.0%}", "sector": hit["sector"], "share": hit["share"]}
        if body in group:
            return {"ref": ref, "kind": "counterparty", "title": body, "text": f"Компания той же группы: {body}"}
    raise RefNotFound(f"ссылка не найдена: {ref}")
