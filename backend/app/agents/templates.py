"""STUB и запасной вариант интерпретатора: шесть блоков по шаблонам из фактов, признаков и тезисов банка.

Используется (1) как ответ модели шага interpret в режиме LLM_MODE=stub и (2) как FALLBACK, если модель
в режиме real недоступна или дважды вернула невалидный ответ. Контракт тот же, что у модели: у каждого
утверждения есть label и refs, выводы ИИ ссылаются и на признаки компании, и на источники.
Тексты — заготовки по темам и признакам; качество формулировок не равно ответу модели.
Замена: LLM_MODE=real (промпт prompts/interpret.md), этот модуль остаётся запасным вариантом.
"""
import re

UP = re.compile(r"вырос|выросл|подорож|повыш|рост|увелич|ускор|превысил|обновил", re.I)
DOWN = re.compile(r"снизил|снижен|подешев|упал|сократ|замедл|опустил|ослаб\w* спрос", re.I)
EASING = re.compile(r"льгот|продл|упрост|поддерж|отмен|сниж\w* ставк", re.I)

PRODUCERS = {"oil": {"oil_gas"}, "gold": {"gold_mining"}, "metals": {"mining_metals", "metals_trade"},
             "grain": {"agriculture"}}
COMMODITY_TITLES = {"oil": "нефть и топливо", "gold": "золото", "metals": "металлы", "grain": "зерно"}
EXPORT_SECTORS = {"oil_gas", "gold_mining", "mining_metals", "agriculture", "chemicals_pharma"}
IMPORT_SECTORS = {"wholesale_trade", "food_trade", "pharma_trade", "auto", "retail", "machinery", "light_industry"}


def _claim(cid, text, label, refs, conf=0.7):
    return {"id": cid, "text": text, "label": label, "refs": list(dict.fromkeys(refs)), "confidence": conf}


def _direction(event) -> str:
    text = " ".join(f"{i['title']} {i['text']}" for i in event["items"][:1])
    up, down = len(UP.findall(text)), len(DOWN.findall(text))
    return "up" if up > down else "down" if down > up else "flat"


def generate(data: dict) -> dict:
    """data — контекст интерпретатора (см. interpreter.build_context). Возвращает черновик блоков."""
    ev, co, feats = data["event"], data["company"], data["features"]
    topic, issues = ev["topic"], data.get("issues", [])
    # утверждения шаблона строятся из дословных цитат, поэтому number_mismatch исправляется перегенерацией;
    # остальные замечания (битая ссылка, слух, противоречие) убирают утверждение
    bad_ids = {i["claim_id"] for i in issues if i.get("claim_id") and i["type"] != "number_mismatch"}
    has = lambda n: feats.get(n, {}).get("value") is True  # noqa: E731
    facts = ev["facts"]
    stated = [f for f in facts if f["modality"] != "speculation"]
    src = (stated or facts)[0]["ref"] if facts else ev["news_ref"]
    sector = co["sector_title"]
    exps = {e["name"]: e for e in data["exposures"]}
    commodity = (ev.get("commodities") or [None])[0]
    direction = _direction(ev)

    # 1. Что произошло: факты из источников
    what, seen = [], set()
    for k, f in enumerate(facts, start=1):
        key = (tuple(f["values"]), f["date"])
        if key in seen and (f["values"] or f["date"]):  # тот же факт из пересказа в другом источнике
            continue
        seen.add(key)
        if f["modality"] == "speculation":
            what.append(_claim(f"w{k}", f"Непроверенное утверждение источника: {f['quote']}", "fact", [f["ref"]], 0.3))
        else:
            what.append(_claim(f"w{k}", f["quote"], "fact", [f["ref"]], 0.9 if f["modality"] == "stated" else 0.7))
        if len(what) == 3:
            break

    # 2. Почему важно именно этой компании: связь события с признаками
    why = []
    lead = {
        "rate": "Ставка определяет стоимость заёмных денег для компании",
        "fx": "Курс рубля влияет на компанию через внешнеторговые расчёты",
        "commodities": f"Цены на {COMMODITY_TITLES.get(commodity, 'сырьё')} отражаются на выручке и затратах компании",
        "inflation": "Рост цен увеличивает операционные издержки компании",
        "regulation": f"Изменение правил касается отрасли «{sector}»",
        "taxes": f"Налоговые решения меняют нагрузку на компании отрасли «{sector}»",
        "sanctions_trade": "Ограничения во внешней торговле затрагивают расчёты и поставки компании",
        "industry": f"Спрос в отрасли «{sector}» напрямую влияет на выручку компании",
        "capital_markets": "Условия долгового рынка определяют стоимость и доступность финансирования компании",
        "other": "Событие имеет общий характер",
    }[topic]
    for name in data["matched_exposures"]:
        e = exps.get(name)
        if e:
            refs = [f"exp:{name}"] + [f"feat:{b}" for b in e["based_on"] if b in feats] + [src]
            why.append(_claim(f"y{len(why) + 1}", f"{lead}. {e['explanation']}", "model_inference", refs, 0.75))
    if data.get("sector_hit"):
        why.append(_claim(f"y{len(why) + 1}", f"Событие напрямую касается отрасли компании — «{sector}».",
                          "model_inference", ["feat:sector", src], 0.8))
    if data.get("geo_countries"):
        why.append(_claim(f"y{len(why) + 1}", "В событии упомянуты страны, с которыми компания ведёт внешнюю торговлю: "
                          f"{', '.join(data['geo_countries'])}.", "model_inference", ["feat:fts_countries", src], 0.75))
    feat_refs = {r for c in why for r in c["refs"] if r.startswith(("feat:", "exp:"))}
    if len(feat_refs) < 2:  # требование: связать событие минимум с двумя признаками компании
        why.append(_claim(f"y{len(why) + 1}", f"Компания работает в отрасли «{sector}» (регион: {co['region']}); "
                          "прямой связи события с её продуктами и операциями не найдено, влияние фоновое.",
                          "model_inference", ["feat:sector", "feat:region", src], 0.5))

    # 3. Последствия: риски и возможности
    risks, opps = [], []
    debt = has("has_loans") or has("has_leasing") or has("has_factoring")
    debt_refs = [f"feat:{n}" for n in ("has_loans", "has_leasing", "has_factoring") if has(n)]
    exporter = co["sector"] in EXPORT_SECTORS and has("fts_flag")
    importer = co["sector"] in IMPORT_SECTORS and has("fts_flag")
    if topic in ("rate", "capital_markets"):
        if debt:
            risks.append(("Расходы на обслуживание долга останутся высокими: новые кредиты, лизинг и рефинансирование "
                          "будут дорогими.", debt_refs))
        if co["sector"] in ("construction", "real_estate", "auto", "finance_leasing"):
            risks.append(("Дорогой кредит сдерживает спрос клиентов отрасли, которые покупают в кредит или ипотеку.",
                          ["feat:sector"]))
        if has("has_deposits") or not debt:
            opps.append(("Высокие ставки позволяют получать доход на свободную ликвидность.",
                         ["feat:has_deposits"] if has("has_deposits") else ["feat:has_loans"]))
        opps.append(("Пауза в изменении ставки даёт время спокойно зафиксировать условия финансирования.",
                     debt_refs or ["feat:sector"]))
    elif topic == "fx":
        if importer:
            risks.append(("Слабый рубль удорожает импортные закупки в рублях и давит на маржу.", ["feat:fts_flag", "feat:fts_countries"]))
        if exporter:
            opps.append(("Ослабление рубля увеличивает рублёвую выручку от экспорта.", ["feat:fts_flag", "feat:sector"]))
        risks.append(("Колебания курса усложняют планирование бюджета и цен.", ["feat:fts_flag"]))
        if not exporter:
            opps.append(("Отечественные поставщики могут стать конкурентнее импортных.", ["feat:sector"]))
    elif topic == "commodities":
        producer = co["sector"] in PRODUCERS.get(commodity, set())
        good = (direction == "up") == producer
        text_r = "Неблагоприятная динамика цен на {c} может ухудшить финансовый результат компании."
        text_o = "Благоприятная динамика цен на {c} может улучшить финансовый результат компании."
        c = COMMODITY_TITLES.get(commodity, "сырьё")
        (opps if good else risks).append(((text_o if good else text_r).format(c=c), ["exp:commodity_links", "feat:sector"]))
        (risks if good else opps).append(("Цены на сырьё волатильны: эффект может развернуться в следующих кварталах.",
                                          ["exp:commodity_links"]))
    elif topic == "inflation":
        risks.append(("Рост цен у поставщиков и расходов на персонал увеличит издержки.",
                      ["exp:inflation_sensitivity"] + (["feat:has_payroll"] if has("has_payroll") else [])))
        opps.append(("Компания может пересмотреть цены и условия индексации в договорах с покупателями.", ["feat:sector"]))
    elif topic in ("regulation", "taxes"):
        eased = bool(EASING.search(" ".join(i["text"] for i in ev["items"])))
        if eased:
            opps.append(("Изменения могут снизить нагрузку на компанию или сохранить для неё льготы.", ["feat:sector"]))
        else:
            risks.append(("Новые требования или налоги увеличат расходы и потребуют подготовки.", ["feat:sector"]))
        risks.append(("Срок вступления изменений в силу нужно учесть в финансовом плане.", ["exp:regulation_sensitivity"]))
    elif topic == "sanctions_trade":
        risks.append(("Возможны задержки платежей и поставок, рост комиссий и стоимости логистики.",
                      ["feat:fts_flag", "exp:sanctions_exposure"]))
        if EASING.search(" ".join(i["text"] for i in ev["items"])):
            opps.append(("Упрощение логистики открывает более дешёвые маршруты поставок.", ["feat:fts_countries"]))
    elif topic == "industry":
        if direction == "down":
            risks.append(("Снижение спроса в отрасли может уменьшить продажи компании.", ["exp:demand_sensitivity", "feat:sector"]))
        else:
            opps.append(("Рост спроса в отрасли может увеличить продажи компании.", ["exp:demand_sensitivity", "feat:sector"]))
    if not risks and not opps:
        risks.append(("Прямых последствий для компании не выявлено; событие стоит отслеживать.", ["feat:sector"]))
    risks_c = [_claim(f"r{k}", t, "model_inference", r + [src], 0.6) for k, (t, r) in enumerate(risks, 1)]
    opps_c = [_claim(f"o{k}", t, "model_inference", r + [src], 0.6) for k, (t, r) in enumerate(opps, 1)]

    # 4. Действия и вопросы для анализа (допустимы продукты банка)
    acts = []
    if topic in ("rate", "capital_markets"):
        if debt:
            acts.append(("Проверить долю кредитов и лизинга с плавающей ставкой и обсудить с банком фиксацию ставки "
                         "или хеджирование процентного риска.", debt_refs))
        acts.append(("Разместить свободную ликвидность на депозите или в инструментах денежного рынка Альфа-Банка, "
                     "пока ставки высокие.", ["feat:has_deposits"]))
    elif topic in ("fx", "sanctions_trade"):
        if importer or has("fts_flag"):
            acts.append(("Рассмотреть валютные форварды на ближайшие закупки и проверить платёжные маршруты "
                         "с банком; для крупных поставок — аккредитив.", ["feat:fts_flag", "feat:fts_countries"]))
        if exporter:
            acts.append(("Спланировать график продажи валютной выручки.", ["feat:fts_flag"]))
    elif topic == "commodities":
        acts.append(("Оценить чувствительность бюджета к цене сырья и рассмотреть фиксацию цен с контрагентами "
                     "или хеджирование.", ["exp:commodity_links"]))
    elif topic == "inflation":
        acts.append(("Пересмотреть бюджет закупок и условия индексации цен в договорах.", ["exp:inflation_sensitivity"]))
    elif topic in ("regulation", "taxes"):
        acts.append(("Оценить эффект изменений на финансовый план и подготовиться к сроку вступления в силу.",
                     ["feat:sector"]))
    elif topic == "industry":
        acts.append(("Скорректировать план продаж и запасов с учётом динамики спроса.", ["exp:demand_sensitivity"]))
    if not acts:
        acts.append(("Специальных действий не требуется; событие стоит отслеживать.", ["feat:sector"]))
    if data.get("questions"):
        acts.append((f"Вопрос для анализа: {data['questions'][0]}", ["feat:sector"]))
    acts_c = [_claim(f"a{k}", t, "model_inference", r + [src], 0.6) for k, (t, r) in enumerate(acts, 1)]

    # Исправление по замечаниям проверки: проблемные утверждения убираются, пустые блоки явно помечаются
    def keep(claims):
        return [c for c in claims if c["id"] not in bad_ids]
    draft = {"what_happened": keep(what), "why_it_matters": keep(why), "risks": keep(risks_c),
             "opportunities": keep(opps_c), "actions": keep(acts_c)}
    for block in ("what_happened", "why_it_matters", "actions"):
        if not draft[block]:
            draft[block] = [_claim(f"{block[0]}0", "Недостаточно данных для этого блока: надёжных источников не найдено.",
                                   "model_inference", ["feat:sector", ev["news_ref"]], 0.2)]
    if not draft["risks"] and not draft["opportunities"]:
        draft["risks"] = [_claim("r0", "Недостаточно данных, чтобы оценить последствия.", "model_inference",
                                 ["feat:sector", ev["news_ref"]], 0.2)]
    # ссылки на признаки, которых нет в профиле, не отдаём
    known = {f"feat:{n}" for n in feats} | {f"exp:{n}" for n in exps}
    for block in draft.values():
        for c in block:
            c["refs"] = [r for r in c["refs"] if not r.startswith(("feat:", "exp:")) or r in known]
    return draft
