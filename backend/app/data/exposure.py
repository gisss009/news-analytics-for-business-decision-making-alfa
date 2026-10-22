"""Производные признаки чувствительности компании к макрофакторам (0..1) с объяснением и основаниями.

Правила и веса в exposure.yaml. Основания (based_on) — имена признаков профиля и показателей графа;
refs — ссылки feat:* / cp:* для трассировки. Ссылка на сам признак: exp:<name>.
Запуск: python -m app.data.exposure U_S0001
"""
import sys
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from app.data import graph
from app.data.okved import sector_of
from app.data.profile import profile_dict

CONFIG_PATH = Path(__file__).resolve().parent / "exposure.yaml"
COMMODITY_TITLES = {"oil": "нефть", "metals": "металлы", "gold": "золото", "grain": "зерно"}


class Exposure(BaseModel):
    name: str
    score: float = Field(ge=0, le=1)
    explanation: str
    based_on: list[str]
    refs: list[str]
    details: dict = {}


@lru_cache
def config(path: Path = CONFIG_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _clip(x: float) -> float:
    return round(max(0.0, min(1.0, x)), 3)


def _level(score: float) -> str:
    return "высокий" if score >= 0.66 else "средний" if score >= 0.33 else "низкий"


def exposures(company_id: str) -> list[Exposure]:
    cfg = config()
    p = profile_dict(company_id)
    sector = sector_of(p["okved_code"].value)
    sf = sector.factors
    on = lambda name: bool(p[name].value) and not p[name].missing  # noqa: E731
    out: list[Exposure] = []

    def add(name: str, score: float, text: str, based_on: list[str], extra_refs: list[str] = (), details=None):
        refs = [f"feat:{b}" for b in based_on if b in p] + list(extra_refs)
        out.append(Exposure(name=name, score=_clip(score), explanation=f"Уровень {_level(_clip(score))}: {text}",
                            based_on=based_on, refs=refs, details=details or {}))

    # ставка
    c = cfg["rate_sensitivity"]
    prods = [k for k in c["products"] if on(k)]
    score = sf["rate"] * c["sector_weight"] + sum(c["products"][k] for k in prods)
    names = {"has_loans": "кредиты", "has_leasing": "лизинг", "has_factoring": "факторинг", "has_guarantees": "гарантии"}
    text = (f"отрасль «{sector.title}» зависит от ставки ({sf['rate']:.1f})"
            + (f"; долговые продукты: {', '.join(names[k] for k in prods)}" if prods else "; кредитов и лизинга в банке нет"))
    add("rate_sensitivity", score, text, ["sector", *prods] if prods else ["sector", "has_loans", "has_leasing"])

    # валюта
    c = cfg["fx_exposure"]
    countries = p["fts_countries"].value or []
    score = (c["fts_flag"] if on("fts_flag") else 0) + min(c["max_countries_bonus"], c["per_country"] * len(countries)) \
        + sf["fx"] * c["sector_weight"] + (c["foreign_ownership"] if on("foreign_ownership") else 0)
    text = (f"ВЭД со странами: {', '.join(countries)}" if countries else "ВЭД по данным ФТС нет") + \
        f"; валютная чувствительность отрасли {sf['fx']:.1f}"
    add("fx_exposure", score, text, ["fts_flag", "fts_countries", "sector"]
        + (["foreign_ownership"] if on("foreign_ownership") else []))

    # сырьё
    c = cfg["commodity_links"]
    sup = graph.counterparties(company_id, "suppliers", top=10) + graph.counterparties(company_id, "buyers", top=10)
    cp_scores, cp_refs = {}, []
    for cm in c["commodities"]:
        linked = [e for e in sup if e["sector"] and sector_of_name(e["sector"]).factors[cm] >= 0.8]
        cp_scores[cm] = sum(e["share"] for e in linked) / 2  # доля среди поставщиков и покупателей
        cp_refs += [e["ref"] for e in linked]
    per = {cm: _clip(sf[cm] * c["sector_weight"] + cp_scores[cm] * c["counterparty_weight"]) for cm in c["commodities"]}
    top = max(per, key=per.get)
    strong = [COMMODITY_TITLES[k] for k, v in per.items() if v >= 0.5]
    text = (f"цены на {', '.join(strong)} влияют через отрасль" if strong else "прямой зависимости от цен сырья нет") + \
        (f" и контрагентов ({len(set(cp_refs))})" if cp_refs else "")
    add("commodity_links", per[top], text, ["sector"], sorted(set(cp_refs)), details={"by_commodity": per})

    # концентрация поставщиков
    c = cfg["supply_concentration"]
    conc = graph.concentration(company_id)
    share = conc["suppliers_top3_share"]
    score = (share - c["share_low"]) / (c["share_high"] - c["share_low"])
    if 0 < conc["suppliers_count"] < c["min_suppliers"]:
        score += 0.2
    top_sup = graph.counterparties(company_id, "suppliers", top=3)
    text = (f"на топ-3 поставщиков приходится {share:.0%} закупок ({conc['suppliers_count']} поставщиков)"
            if conc["suppliers_count"] else "данных о поставщиках в платежах нет")
    add("supply_concentration", score if conc["suppliers_count"] else 0.0, text, ["suppliers_top3_share"],
        [e["ref"] for e in top_sup], details=conc)

    # регион
    c = cfg["region_risk"]
    region = p["region"].value
    score = c["regions"].get(region, c["default"])
    add("region_risk", score, f"регион: {region or 'нет данных'}", ["region"])

    # группа
    c = cfg["group_dependency"]
    gl = graph.group_links(company_id)
    n = len(gl["members"])
    score = min(c["max_members_score"], c["per_member"] * n) + gl["intra_group_share"] * c["intra_share_weight"]
    text = (f"в группе ещё {n} компаний, внутригрупповые платежи {gl['intra_group_share']:.0%} объёма"
            if n else "других компаний группы в данных нет")
    add("group_dependency", score, text, ["group_id", "group_size"], [f"cp:{m}" for m in gl["members"][:5]])

    # инфляция, спрос, санкции, регулирование
    c = cfg["inflation_sensitivity"]
    score = sf["inflation"] * c["sector_weight"] + sum(v for k, v in c["products"].items() if on(k))
    add("inflation_sensitivity", score, f"инфляция издержек в отрасли ({sf['inflation']:.1f})"
        + ("; есть зарплатный проект — расходы на персонал" if on("has_payroll") else ""), ["sector", "has_payroll"])
    add("demand_sensitivity", sf["demand"] * cfg["demand_sensitivity"]["sector_weight"],
        f"зависимость отрасли от потребительского спроса ({sf['demand']:.1f})", ["sector"])
    c = cfg["sanctions_exposure"]
    score = sf["sanctions"] * c["sector_weight"] + (c["fts_flag"] if on("fts_flag") else 0) \
        + (c["foreign_ownership"] if on("foreign_ownership") else 0)
    add("sanctions_exposure", score, f"санкционная чувствительность отрасли {sf['sanctions']:.1f}"
        + ("; есть ВЭД" if on("fts_flag") else ""), ["sector", "fts_flag", "foreign_ownership"])
    add("regulation_sensitivity", sf["regulation"] * cfg["regulation_sensitivity"]["sector_weight"],
        f"зависимость отрасли от регулирования и тарифов ({sf['regulation']:.1f})", ["sector"])
    return out


@lru_cache
def sector_of_name(name: str):
    """Отрасль по имени (для контрагентов, у которых уже известна отрасль)."""
    from app.data.okved import all_sectors
    return {s.name: s for s in all_sectors()}[name]


def exposure_dict(company_id: str) -> dict[str, Exposure]:
    return {e.name: e for e in exposures(company_id)}


if __name__ == "__main__":
    for e in exposures(sys.argv[1]):
        print(f"{e.name:<24} {e.score:.2f}  {e.explanation}  refs={e.refs}")
