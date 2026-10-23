"""Шаг Interpreter: шесть блоков интерпретации события для конкретной компании.

Модель шага interpret (GLM) получает только контекст из RunState (без инструментов) и возвращает черновик
пяти блоков; позицию банка (bank_view) добавляет система из материалов банка, basis собирается из ссылок.
Ответ проверяется схемой Claim (label и refs). При ошибке модели — шаблонный FALLBACK (agents/templates.py).
STUB: в режиме stub ответ модели строится теми же шаблонами.
"""
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.agents import templates
from app.agents.ranker import CompanyContext, event_commodities
from app.agents.schemas import BankViewBlock, Blocks, Claim, ClaimsBlock, ConsequencesBlock, Relevance
from app.core.logging import get_logger
from app.data.okved import all_sectors
from app.llm import stubs
from app.llm.client import LLMError, complete, data_block

PROMPT = (Path(__file__).resolve().parent / "prompts" / "interpret.md").read_text(encoding="utf-8")
PROMPT_VERSION = "interp-v1"
log = get_logger("interpreter")

CONTEXT_FEATURES = ("sector", "region", "revenue_rub", "large_company", "has_loans", "has_leasing", "has_guarantees",
                    "has_factoring", "has_deposits", "has_payroll", "has_rko", "fts_flag", "fts_countries",
                    "group_size", "cl_type", "eco_stage")


class Draft(BaseModel):
    what_happened: list[Claim] = []
    why_it_matters: list[Claim] = []
    risks: list[Claim] = []
    opportunities: list[Claim] = []
    actions: list[Claim] = []


class _RawDraft(BaseModel):
    """Ответ модели до проверки утверждений по одному: одно плохое утверждение не должно губить весь ответ."""
    what_happened: list[dict] = []
    why_it_matters: list[dict] = []
    risks: list[dict] = []
    opportunities: list[dict] = []
    actions: list[dict] = []


def _accept(raw: _RawDraft) -> Draft:
    """Оставляет только утверждения, прошедшие схему Claim (метка и ссылки); без «Что произошло» — ошибка."""
    out, dropped = {}, []
    for block in Draft.model_fields:
        out[block] = []
        for c in getattr(raw, block):
            try:
                out[block].append(Claim.model_validate(c))
            except ValidationError as e:
                dropped.append(f"{block}:{c.get('id', '?')}: {e.errors()[0]['msg'][:120]}")
    if dropped:
        log.warning("interpret_claims_dropped", extra={"dropped": dropped})
    if not out["what_happened"]:
        raise LLMError("interpret: не осталось утверждений «Что произошло»: " + "; ".join(dropped)[:300])
    return Draft(**out)


stubs.register("interpret", lambda messages, data: templates.generate(data))


def build_context(event: dict, cc: CompanyContext, relevance: Relevance, bank_used: list[dict], role: str,
                  questions: list[str] | None = None, related: list[dict] | None = None) -> dict:
    """Всё, что интерпретатор знает о запуске. Внешние тексты пойдут в промпт только через data_block()."""
    sector_name = cc.features["sector"]["value"]
    sector_title = next((s.title for s in all_sectors() if s.name == sector_name), sector_name)
    matched_exp = [r.split(":", 1)[1] for r in relevance.matched_features if r.startswith("exp:")]
    facts = [{"ref": f["fact_id"], "quote": f["quote"], "values": f["values"], "date": f["date"],
              "modality": f["modality"], "source": it["source_name"]}
             for it in event["items"] for f in it["facts"]]
    lead_codes = {"CN": "КИТАЙ", "TR": "ТУРЦИЯ", "KZ": "КАЗАХСТАН", "UZ": "УЗБЕКИСТАН", "AE": "ОАЭ"}
    countries = cc.features["fts_countries"]["value"] or []
    geo_countries = [c for c in countries if c in {lead_codes.get(g) for g in event["geo"]}]
    return {
        "role": role,
        "company": {"name": cc.name, "sector": sector_name, "sector_title": sector_title,
                    "region": cc.features["region"]["value"]},
        "features": {n: {"title": cc.features[n]["title"], "value": cc.features[n]["value"],
                         "missing": cc.features[n]["missing"]} for n in CONTEXT_FEATURES if n in cc.features},
        "exposures": [{"name": e["name"], "ref": f"exp:{e['name']}", "score": e["score"], "explanation": e["explanation"],
                       "based_on": e["based_on"]} for e in cc.exposures.values()],
        "matched_exposures": matched_exp,
        "sector_hit": relevance.components.get("sector") == 1.0,
        "geo_countries": geo_countries,
        "event": {"id": event["event_id"], "title": event["title"], "topic": event["topic"],
                  "first_seen": event["first_seen"], "news_ref": f"news:{event['items'][0]['item_id']}",
                  "facts": facts, "commodities": event_commodities(event) if event["topic"] == "commodities" else [],
                  "items": [{"ref": f"news:{i['item_id']}", "title": i["title"], "text": i["text"],
                             "source": i["source_name"], "source_type": i["source_type"]} for i in event["items"]]},
        "relevance": {"score": relevance.score, "reasons": relevance.reasons},
        "bank_view": [{"ref": u["ref"], "thesis": u["thesis"], "quote": u["quote"]} for u in bank_used],
        "questions": questions or [],
        "related": related or [],
        "issues": [],
    }


def interpret(context: dict, bank_block: BankViewBlock) -> tuple[Blocks, str]:
    """Возвращает блоки и способ получения: llm | stub | fallback."""
    msgs = [{"role": "system", "content": PROMPT}, {"role": "user", "content": data_block(context)}]
    method = "stub"
    try:
        draft = _accept(complete("interpret", msgs, schema=_RawDraft))
        method = "llm" if not _stub_mode() else "stub"
    except LLMError as e:
        log.warning("interpret_fallback", extra={"error": str(e)[:200]})
        draft = Draft.model_validate(templates.generate(context))
        method = "fallback"
    blocks = Blocks(what_happened=ClaimsBlock(claims=draft.what_happened),
                    why_it_matters=ClaimsBlock(claims=draft.why_it_matters),
                    consequences=ConsequencesBlock(risks=draft.risks, opportunities=draft.opportunities),
                    actions=ClaimsBlock(claims=draft.actions), bank_view=bank_block).collect_basis()
    return blocks, method


def _stub_mode() -> bool:
    from app.core.config import settings
    return settings.llm_mode == "stub"
