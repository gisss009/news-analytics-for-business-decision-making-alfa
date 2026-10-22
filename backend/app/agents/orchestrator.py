"""Оркестратор: собственный цикл агентного ядра (без агентных фреймворков).

Planner → Retriever (инструменты) → Ranker → BankView → Interpreter → Verifier.
Если проверка нашла замечания: целевой поиск по проблемным утверждениям и перегенерация с передачей замечаний,
не больше MAX_VERIFY_ITERATIONS попыток. Если замечания остались — проблемные утверждения не отдаются,
а результат помечается DONE_WITH_WARNINGS. Ошибка модели → шаблонный FALLBACK с пометкой.
Каждый шаг пишет TraceStep в RunState; состояние сохраняется после каждого шага.
Запуск: python -m app.agents.orchestrator U_S0001 ev_n001 [cfo]
"""
import sys
from datetime import datetime

from app.agents import state as state_store
from app.agents.bank_view import bank_view
from app.agents.events import get_event
from app.agents.interpreter import PROMPT_VERSION, build_context, interpret
from app.agents.planner import execute_plan, make_plan
from app.agents.ranker import company_context, score_event
from app.agents.schemas import (Blocks, ClaimsBlock, ClientFeature, ConsequencesBlock, EventRef, Insight, SourceLink,
                                Verification)
from app.agents.state import RunState
from app.agents.tools import ToolContext, call_tool
from app.agents.verifier import verify
from app.core.config import settings
from app.core.db import session
from app.core.logging import run_id_var

NO_DATA_PREFIX = "Недостаточно данных"
BLOCK_TITLES = {"what_happened": "Что произошло", "why_it_matters": "Почему это важно", "consequences": "Последствия",
                "actions": "Действия", "bank_view": "Оценка банка"}


def _drop_claims(blocks: Blocks, ids: set[str]) -> Blocks:
    keep = lambda cs: [c for c in cs if c.id not in ids]  # noqa: E731
    return Blocks(what_happened=ClaimsBlock(claims=keep(blocks.what_happened.claims)),
                  why_it_matters=ClaimsBlock(claims=keep(blocks.why_it_matters.claims)),
                  consequences=ConsequencesBlock(risks=keep(blocks.consequences.risks),
                                                 opportunities=keep(blocks.consequences.opportunities)),
                  actions=ClaimsBlock(claims=keep(blocks.actions.claims)), bank_view=blocks.bank_view).collect_basis()


def _repair_search(state: RunState, issues: list, context: dict) -> None:
    """missing_ref / unsupported → целевой поиск по тексту проблемного утверждения."""
    targets = [i for i in issues if i.type in ("missing_ref", "unsupported") and i.claim_id]
    if not targets:
        return
    ctx = ToolContext(company_id=state.company_id, step="retriever", run_id=state.run_id)
    with state.step("repair_search", claims=[i.claim_id for i in targets]) as info:
        found = []
        for i in targets:
            hits = call_tool(ctx, "news_search", query=i.detail, k=3)
            found += [{"ref": h["ref"], "title": h["title"], "snippet": h["snippet"]} for h in hits]
        context["related"] = context.get("related", []) + found
        info["found"] = len(found)


def _tokens(run_id: str) -> int:
    with session() as conn:
        return conn.execute("SELECT COALESCE(SUM(tokens), 0) FROM tool_calls WHERE run_id = ?", (run_id,)).fetchone()[0]


def run_insight(company_id: str, event_id: str, role: str = "cfo") -> RunState:
    state = RunState(company_id=company_id, event_id=event_id, role=role)
    token = run_id_var.set(state.run_id)
    try:
        state_store.save(state)
        event = get_event(event_id)
        cc = company_context(company_id, state.run_id)
        brief = {"name": cc.name, "sector": cc.features["sector"]["value"],
                 "top_exposures": sorted(((e["name"], e["score"]) for e in cc.exposures.values()), key=lambda x: -x[1])[:4]}

        make_plan(state, event, brief)
        state_store.save(state)
        execute_plan(state)
        state_store.save(state)
        own = {f"news:{i['item_id']}" for i in event["items"]}
        related = [{"ref": h["ref"], "title": h["title"], "snippet": h["snippet"]}
                   for r in state.tool_results if r.ok and r.tool == "news_search" for h in r.result
                   if h["ref"] not in own]

        with state.step("ranker") as info:
            state.relevance = score_event(cc, event, role)
            info.update(score=state.relevance.score, matched=state.relevance.matched_features)
        state.status = "RANKED"

        with state.step("bank_view") as info:
            bank_block, bank_used = bank_view(event, company_id, state.run_id)
            info.update(absent=bank_block.absent, theses=[u["thesis_id"] for u in bank_used])

        context = build_context(event, cc, state.relevance, bank_used, role,
                                questions=state.plan.questions if state.plan else [], related=related)
        state.context = {"event_title": event["title"], "bank_theses": bank_used, "related": related}

        max_iter = max(1, settings.max_verify_iterations)
        method, blocks, verification = "stub", None, None
        for it in range(1, max_iter + 1):
            state.iterations = it
            with state.step("interpreter", iteration=it) as info:
                blocks, method = interpret(context, bank_block)
                info.update(method=method, claims=len(blocks.all_claims()))
                if method == "fallback":
                    info["_status"] = "fallback"
            state.status = "VERIFYING"
            with state.step("verifier", iteration=it) as info:
                verification = verify(blocks, company_id, state.run_id, iteration=it)
                info.update(passed=verification.passed, issues=[i.model_dump() for i in verification.issues])
            state.verifications.append(verification)
            state_store.save(state)
            if verification.passed:
                break
            if it < max_iter:
                context["issues"] = [i.model_dump() for i in verification.issues]
                _repair_search(state, verification.issues, context)

        warnings: list[str] = []
        if not verification.passed:
            bad = {i.claim_id for i in verification.issues if i.claim_id}
            blocks = _drop_claims(blocks, bad)
            for i in verification.issues:
                where = BLOCK_TITLES.get((i.block or "").split(".")[0], i.block or "инсайт")
                warnings.append(f"{where}: {i.detail}" + (" — утверждение не показано" if i.claim_id else ""))
        for name, c in blocks.all_claims():
            if c.text.startswith(NO_DATA_PREFIX):
                warnings.append(f"{BLOCK_TITLES.get(name.split('.')[0], name)}: недостаточно данных")
        if blocks.bank_view.absent:
            warnings.append("Оценка банка: позиция по теме в материалах не представлена")
        if method == "fallback":
            warnings.insert(0, "Модель недоступна: интерпретация собрана по шаблону из фактов и признаков")
        if "blog" in event["source_types"]:
            warnings.append("Источник события — анонимный блог: факты не подтверждены")

        status = "FALLBACK" if method == "fallback" else ("DONE" if verification.passed else "DONE_WITH_WARNINGS")
        used_feats = {r.split(":", 1)[1] for r in blocks.basis.refs if r.startswith("feat:")}
        state.insight = Insight(
            run_id=state.run_id, company_id=company_id, role=role,
            event=EventRef(id=event["event_id"], title=event["title"], topic=event["topic"],
                           published_at=datetime.fromisoformat(event["first_seen"]),
                           sources=[SourceLink(name=i["source_name"], url=i["url"], ref=f"news:{i['item_id']}")
                                    for i in event["items"]]),
            client_features=[ClientFeature(name=n, value=cc.features[n]["value"], source=cc.features[n]["source"])
                             for n in cc.features if n in used_feats],
            relevance=state.relevance, blocks=blocks,
            verification=Verification(passed=verification.passed, iterations=state.iterations,
                                      issues=verification.issues),
            warnings=list(dict.fromkeys(warnings)), status=status, prompt_version=PROMPT_VERSION)
        state.warnings = state.insight.warnings
        state.status = status
        state.tokens_used = _tokens(state.run_id)
        state_store.save(state)
        return state
    except Exception:
        state.status = "ERROR"
        state_store.save(state)
        raise
    finally:
        run_id_var.reset(token)


if __name__ == "__main__":
    s = run_insight(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "cfo")
    ins = s.insight
    print(f"run {s.run_id}: {s.status}, итераций {s.iterations}, score {ins.relevance.score}, токенов {s.tokens_used}")
    print("шаги:", " → ".join(f"{t.step}({t.status})" for t in s.trace))
    for block, c in ins.blocks.all_claims():
        print(f"[{block}] {c.label}: {c.text[:140]}  {c.refs}")
    for w in ins.warnings:
        print("! ", w)
