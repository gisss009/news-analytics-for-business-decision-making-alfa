"""Шаг BankView: позиция аналитиков банка по теме события — только из материалов банка, с цитатой и страницей.

Тезисы ищутся инструментом analytics_search (фильтр по теме события, устаревшие материалы исключены).
Если подходящих тезисов нет, блок явно сообщает, что позиции банка по теме нет, и ничего не придумывает.
Текст claim — краткое изложение тезиса из материалов (без LLM), ссылки — страница документа и сам тезис.
"""
from app.agents.ranker import config as ranker_config
from app.agents.ranker import event_commodities
from app.agents.schemas import BankViewBlock, Claim
from app.agents.tools import ToolContext, call_tool
from app.ingest.text import stems

MIN_SCORE = 1.5        # порог BM25: ниже — совпадение случайных слов
MIN_SHARED_STEMS = 2   # тезис должен разделять с событием хотя бы 2 содержательных слова
MAX_THESES = 3
ABSENT_NOTE = "Позиция аналитиков банка по этой теме в доступных материалах не представлена."
# слова, совпадение по которым ничего не говорит о близости темы
GENERIC = set(stems("январь февраль март апрель май июнь июль август сентябрь октябрь ноябрь декабрь январе феврале "
                    "марте апреле мае июне июле августе сентябре октябре ноябре декабре года году конец концу рост "
                    "выросли вырос выросла снизились снизился снижение упали упал упало уровне уровень неделю "
                    "месяцев месяц"))


def _shared(a: str, b: str) -> set[str]:
    return {s for s in set(stems(a)) & set(stems(b)) if len(s) >= 3 and s not in GENERIC}


def relevant(hit: dict, event: dict, event_text: str) -> bool:
    """Тезис действительно о том же: для сырья — тот же товар, для остальных тем — общие содержательные слова."""
    thesis_text = f"{hit['extra']['thesis']} {hit['snippet']}".lower()
    if event["topic"] == "commodities":
        kws = ranker_config()["commodity_keywords"]
        return any(k in thesis_text for c in event_commodities(event) for k in kws[c])
    return len(_shared(event_text, thesis_text)) >= MIN_SHARED_STEMS


def bank_view(event: dict, company_id: str, run_id: str | None = None) -> tuple[BankViewBlock, list[dict]]:
    """Возвращает блок позиции банка и использованные тезисы (с цитатами) для контекста интерпретации."""
    if event["topic"] == "other":
        return BankViewBlock(absent=True, note=ABSENT_NOTE), []
    ctx = ToolContext(company_id=company_id, step="bank_view", run_id=run_id)
    lead = event["items"][0]
    query = " ".join([event["title"], lead["text"]])
    hits = call_tool(ctx, "analytics_search", query=query, k=8, filters={"topic": event["topic"]})
    seen, chosen = set(), []
    for h in hits:
        tid = h["extra"]["thesis_id"]
        if h["score"] < MIN_SCORE or tid in seen or not relevant(h, event, query):
            continue
        seen.add(tid)
        chosen.append(h)
        if len(chosen) == MAX_THESES:
            break
    if not chosen:
        return BankViewBlock(absent=True, note=ABSENT_NOTE), []
    chosen.sort(key=lambda h: (h["date"], h["score"]), reverse=True)  # свежие материалы первыми
    claims, used = [], []
    for k, h in enumerate(chosen, start=1):
        ex = h["extra"]
        claims.append(Claim(id=f"b{k}", text=ex["thesis"], label="bank_analytics", confidence=0.9,
                            refs=[h["ref"], f"thesis:{ex['thesis_id']}"]))
        used.append({"thesis_id": ex["thesis_id"], "ref": h["ref"], "thesis": ex["thesis"], "quote": h["snippet"],
                     "doc_title": h["title"], "date": h["date"], "horizon": ex.get("horizon")})
    note = None
    if len({u["date"] for u in used}) > 1:
        note = "Тезисы из материалов разных дат: при расхождении приоритет у более свежего."
    return BankViewBlock(claims=claims, absent=False, note=note), used
