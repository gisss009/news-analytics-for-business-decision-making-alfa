"""Шаг Planner: план сбора данных по событию и компании, исполнение плана инструментами (Retriever).

Модель шага plan предлагает план в JSON; план проверяется схемой и правилами (только разрешённые инструменты,
только компания запуска). Невалидный ответ или недоступная модель → план по умолчанию для темы события.
STUB: в режиме stub модель возвращает план по умолчанию из данных запроса.
"""
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from app.agents.schemas import Plan, PlanStep
from app.agents.state import RunState, ToolResult
from app.agents.tools import STEP_TOOLS, ToolContext, call_tool
from app.core.logging import get_logger
from app.llm import stubs
from app.llm.client import LLMError, complete, data_block

PROMPT = (Path(__file__).resolve().parent / "prompts" / "plan.md").read_text(encoding="utf-8")
PROMPT_VERSION = "plan-v1"
log = get_logger("planner")

TOPIC_PLAN = {
    "rate": {"query": "ключевая ставка прогноз кредитование", "graph": None,
             "questions": ["Как изменится стоимость обслуживания долга компании?",
                           "Стоит ли пересмотреть структуру заимствований (плавающая или фиксированная ставка)?"]},
    "fx": {"query": "курс рубля импорт валюта", "graph": "suppliers",
           "questions": ["Как изменение курса скажется на закупках и выручке компании?"]},
    "commodities": {"query": "цены сырьё прогноз", "graph": "suppliers",
                    "questions": ["Через какие статьи (выручка, закупки, логистика) цена сырья влияет на компанию?"]},
    "inflation": {"query": "инфляция цены прогноз", "graph": None,
                  "questions": ["Как рост издержек повлияет на маржу компании?"]},
    "regulation": {"query": "регулирование тарифы лимиты", "graph": None,
                   "questions": ["Какие изменения правил касаются компании и с какого срока?"]},
    "taxes": {"query": "бюджет налоги", "graph": None,
              "questions": ["Как изменится налоговая нагрузка компании?"]},
    "sanctions_trade": {"query": "санкции экспорт импорт логистика", "graph": "suppliers",
                        "questions": ["Затронуты ли цепочки поставок и расчёты компании?"]},
    "industry": {"query": "спрос потребление отрасль", "graph": "buyers",
                 "questions": ["Как изменение спроса в отрасли скажется на выручке компании?"]},
    "capital_markets": {"query": "облигации ОФЗ доходность заимствования", "graph": None,
                        "questions": ["Как условия долгового рынка влияют на возможности заимствований компании?"]},
    "other": {"query": "", "graph": None, "questions": ["Касается ли событие компании?"]},
}


def default_plan(event: dict, company_id: str) -> Plan:
    topic = event.get("topic") or "other"
    tp = TOPIC_PLAN.get(topic, TOPIC_PLAN["other"])
    first = datetime.fromisoformat(event["first_seen"])
    steps = [
        PlanStep(tool="profile_get", args={"company_id": company_id}, purpose="признаки и чувствительность компании"),
        PlanStep(tool="news_search", purpose="связанные новости в окне ±3 дня",
                 args={"query": event["title"], "k": 5,
                       "filters": {"date_from": (first - timedelta(days=3)).date().isoformat(),
                                   "date_to": (first + timedelta(days=3)).date().isoformat()}}),
    ]
    if topic != "other":
        steps.append(PlanStep(tool="analytics_search", purpose="позиция аналитиков банка по теме",
                              args={"query": f"{event['title']} {tp['query']}", "k": 5, "filters": {"topic": topic}}))
    if tp["graph"]:
        steps.append(PlanStep(tool="graph_query", purpose="контрагенты, через которых событие может затронуть компанию",
                              args={"company_id": company_id, "kind": tp["graph"], "top": 5}))
    return Plan(steps=steps, questions=tp["questions"], source="default")


def validate_plan(plan: Plan, company_id: str) -> Plan:
    allowed = STEP_TOOLS["retriever"]
    for s in plan.steps:
        if s.tool not in allowed:
            raise ValueError(f"инструмент {s.tool} не разрешён")
        if "company_id" in s.args and s.args["company_id"] != company_id:
            raise ValueError("план запрашивает данные другой компании")
    return plan


def _stub_plan(messages, data):
    """STUB: модель «предлагает» план по умолчанию, переданный в данных."""
    return data["default_plan"]


stubs.register("plan", _stub_plan)


def make_plan(state: RunState, event: dict, profile_brief: dict) -> Plan:
    fallback = default_plan(event, state.company_id)
    with state.step("planner") as info:
        msgs = [{"role": "system", "content": PROMPT},
                {"role": "user", "content": data_block({
                    "company_id": state.company_id, "role": state.role, "company": profile_brief,
                    "event": {"title": event["title"], "topic": event["topic"], "sectors": event["sectors"]},
                    "default_plan": fallback.model_dump(exclude={"source"})})}]
        try:
            proposed = complete("plan", msgs, schema=Plan)
            plan = validate_plan(proposed.model_copy(update={"source": "llm"}), state.company_id)
        except (LLMError, ValidationError, ValueError) as e:
            log.warning("plan_fallback", extra={"error": str(e)[:200]})
            plan = fallback
            info["_status"] = "fallback"
        info.update(source=plan.source, steps=[s.tool for s in plan.steps])
    state.plan = plan
    state.status = "PLANNED"
    return plan


def execute_plan(state: RunState) -> list[ToolResult]:
    """Retriever: исполняет шаги плана инструментами; ошибки инструментов не прерывают запуск."""
    ctx = ToolContext(company_id=state.company_id, step="retriever", run_id=state.run_id)
    with state.step("retriever") as info:
        results = []
        for s in state.plan.steps:
            try:
                res = call_tool(ctx, s.tool, **s.args)
                results.append(ToolResult(step="retriever", tool=s.tool, args=s.args, result=res))
            except Exception as e:  # noqa: BLE001 — запуск продолжается без этого шага
                results.append(ToolResult(step="retriever", tool=s.tool, args=s.args, ok=False, error=str(e)[:300]))
        info["calls"] = [f"{r.tool}:{'ok' if r.ok else 'error'}" for r in results]
    state.tool_results += results
    state.status = "RETRIEVED"
    return results
