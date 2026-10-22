"""Извлечение ключевых фактов из новости правилами: предложения с числами или датами.

Fact{fact_id, subject, predicate, values, date, quote, span, modality}. Инвариант: quote == text[span[0]:span[1]],
а каждое значение из values встречается в quote. Модальность: stated (утверждение), expected (прогноз, план,
предложение), speculation (слухи, «может», анонимные оценки). Ссылка на факт в выводах: news:<item_id>#f<n>.
"""
import json
import re

from pydantic import BaseModel

from app.core.db import register_schema, session
from app.ingest.classify import config as classify_config

register_schema("news_facts", """
CREATE TABLE IF NOT EXISTS news_facts (
    fact_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    n INTEGER NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    vals TEXT NOT NULL,
    date TEXT,
    quote TEXT NOT NULL,
    span_start INTEGER NOT NULL,
    span_end INTEGER NOT NULL,
    modality TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_news_facts_item ON news_facts(item_id);
""")

MONTHS = {"январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6, "июл": 7, "август": 8, "сентябр": 9,
          "октябр": 10, "ноябр": 11, "декабр": 12}
_MONTH = r"(январ|феврал|март|апрел|ма|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-я]*"
DATE_DMY = re.compile(r"\b(\d{1,2})\s+" + _MONTH + r"(?:\s+(\d{4})(?:\s+года)?)?", re.I)
DATE_MY = re.compile(r"\b(?:в|за|на|с|до)\s+" + _MONTH + r"\s+(\d{4})", re.I)
UNIT = (r"(?:\s?(?:%|процент\w*|п\.\s?п\.|б\.\s?п\.|базисн\w* пункт\w*|процентн\w* пункт\w*))?"
        r"(?:\s?(?:трлн|млрд|млн|тыс\.|тысяч\w*))?"
        r"(?:\s?(?:руб\w*|доллар\w*|юан\w*|тонн\w*|кв\. м|пункт\w*|посетител\w*|компани\w*))?")
VALUE = re.compile(r"\d+(?:[.,]\d+)?(?:\s?[–-]\s?\d+(?:[.,]\d+)?)?" + UNIT)
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z0-9«\"])")

SPECULATION = re.compile(r"\bмож(ет|ут)\b|возможн|вероятн|уверяет|по слухам|аноним|не приводит", re.I)
EXPECTED = re.compile(r"ожида|прогноз|планир|предлож|обсужда|рассматрива|готовя|будет|вырастут|вступ\w+ в силу|поправк|"
                      r"оценк|по расчётам|по расчетам|по оценк|проект|запланирован", re.I)
# только слова со строчной буквы: глаголы, а не названия в начале предложения
VERB = re.compile(r"(?<![А-ЯЁа-яё])[а-яё]+(?:ил|ила|или|ило|ал|ала|али|ял|яла|яли|ел|ела|ели|ит|ят|ет|ют|ут|ат|ется|ются|"
                  r"ился|илась|ились)(?![А-ЯЁа-яё])")
YEAR = re.compile(r"\b20\d{2}(?:[–-]20\d{2})?(?:\s+год\w*)?")


class Fact(BaseModel):
    fact_id: str
    subject: str
    predicate: str
    values: list[str]
    date: str | None
    quote: str
    span: tuple[int, int]
    modality: str


def sentences(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in SENTENCE.finditer(text):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(text)))
    return [(a, b) for a, b in spans if text[a:b].strip()]


def find_date(sentence: str, default_year: int | None) -> str | None:
    m = DATE_DMY.search(sentence)
    if m:
        day, month = int(m.group(1)), MONTHS[_month_key(m.group(2))]
        year = int(m.group(3)) if m.group(3) else default_year
        return f"{year:04d}-{month:02d}-{day:02d}" if year else f"--{month:02d}-{day:02d}"
    m = DATE_MY.search(sentence)
    if m:
        return f"{int(m.group(2)):04d}-{MONTHS[_month_key(m.group(1))]:02d}"
    m = re.search(r"\b(20\d{2})\s+год", sentence)
    return m.group(1) if m else None


def _month_key(stem: str) -> str:
    stem = stem.lower()
    return next(k for k in MONTHS if stem.startswith(k))


def _subject(sentence: str) -> str:
    low = sentence.lower()
    for name, pat in classify_config()["_entities"]:
        if pat.search(low):
            return name
    words = re.findall(r"[А-ЯЁA-Za-zа-яё\-]+", sentence)
    return " ".join(words[:3])


def extract(item_id: str, text: str, default_year: int | None = None) -> list[Fact]:
    facts = []
    for a, b in sentences(text):
        s = text[a:b]
        dates = [m.span() for pat in (DATE_DMY, DATE_MY, YEAR) for m in pat.finditer(s)]
        # числа, входящие в даты, попадают в поле date, а не в values
        values = [v.group(0).strip() for v in VALUE.finditer(s) if not any(a0 <= v.start() < b0 for a0, b0 in dates)]
        date = find_date(s, default_year)
        if not values and not date:
            continue
        modality = "speculation" if SPECULATION.search(s) else "expected" if EXPECTED.search(s) else "stated"
        verb = VERB.search(s)
        n = len(facts) + 1
        facts.append(Fact(fact_id=f"news:{item_id}#f{n}", subject=_subject(s), predicate=verb.group(0) if verb else "",
                          values=values, date=date, quote=s, span=(a, b), modality=modality))
    return facts


def run() -> dict:
    total = 0
    with session() as conn:
        rows = conn.execute("SELECT item_id, text, published_at FROM news_items").fetchall()
        conn.execute("DELETE FROM news_facts")
        for r in rows:
            for k, f in enumerate(extract(r["item_id"], r["text"], int(r["published_at"][:4])), start=1):
                conn.execute("INSERT INTO news_facts (fact_id, item_id, n, subject, predicate, vals, date, quote, "
                             "span_start, span_end, modality) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (f.fact_id, r["item_id"], k, f.subject, f.predicate, json.dumps(f.values, ensure_ascii=False),
                              f.date, f.quote, f.span[0], f.span[1], f.modality))
                total += 1
    return {"facts": total}


if __name__ == "__main__":
    import sys
    from app.ingest.fixtures import load_fixtures
    fx = {i.id: i for i in load_fixtures(include_holdout=True)}
    for f in extract(sys.argv[1], fx[sys.argv[1]].text, 2026):
        print(f.model_dump())
