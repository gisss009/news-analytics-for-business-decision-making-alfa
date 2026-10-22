"""Темы и отрасли без языковой модели.

Новость или обзор получают метку, если в заголовке или тексте есть устойчивое
словосочетание. Запрос, которым новость нашли, тоже считается голосом за тему:
так карточка про курс не остаётся без темы, даже если формулировка редкая.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    label: str
    query: str
    patterns: tuple[str, ...]


@dataclass(frozen=True)
class Industry:
    label: str
    patterns: tuple[str, ...]


TOPICS: tuple[Topic, ...] = (
    Topic(
        "Ключевая ставка",
        "ключевая ставка Банк России",
        (r"ключев\w+\s+ставк", r"денежно-кредитн", r"ставк\w+\s+цб", r"\bцб рф\b"),
    ),
    Topic(
        "Инфляция",
        "инфляция в России",
        (r"инфляц", r"\bипц\b", r"рост цен"),
    ),
    Topic(
        "Валютные курсы",
        "курс доллара к рублю",
        (
            r"курс\w*\s+доллар",
            r"курс\w*\s+рубл",
            r"курс\w*\s+юан",
            r"курс\w*\s+евро",
            r"доллар\w*/\s*рубл",
            r"доллар\w*.{0,48}рубл",
            r"\busd/?rub\b",
        ),
    ),
    Topic(
        "Сырьё",
        "цены на нефть и золото",
        (
            r"\bнефт(?:ь|и|ью)\b",
            r"\bbrent\b",
            r"золот",
            r"никел",
            r"алюмини",
            r"пшениц",
            r"природн\w+\s+газ",
            r"цен\w+\s+на\s+газ",
        ),
    ),
    Topic(
        "Долг и облигации",
        "доходность ОФЗ",
        (r"\bофз\b", r"облигац", r"доходност\w+\s+(?:офз|облигац)"),
    ),
    Topic(
        "Санкции и дипломатия",
        "санкции против России",
        (r"санкц", r"дипломат", r"геополит", r"экспортн\w+\s+контрол", r"\bofac\b"),
    ),
    Topic(
        "Регулирование",
        "экспортные пошлины России",
        (r"пошлин", r"акциз", r"налогов\w+\s+(?:реформ|нагруз|ставк)", r"\bфас\b", r"регуляторн"),
    ),
    Topic(
        "Рынок труда",
        "рынок труда и безработица в России",
        (r"безработиц", r"рын(?:ок|ка|ке)\s+труда", r"дефицит\w*\s+(?:кадр|персонал)", r"зарплат"),
    ),
    Topic(
        "Спрос",
        "розничные продажи в России",
        (r"розничн\w+\s+(?:продаж|оборот|торговл)", r"потребительск\w+\s+(?:спрос|расход|активн)", r"потреблени"),
    ),
    Topic(
        "Логистика и поставки",
        "логистика и фрахт",
        (r"фрахт", r"логистическ", r"морск\w+\s+порт", r"контейнерн"),
    ),
    Topic(
        "Внешняя торговля",
        "экспорт и импорт России",
        (r"\bэкспорт\b", r"\bимпорт\b", r"торговый баланс", r"таможенн"),
    ),
    Topic(
        "Энергетика",
        "тарифы на электроэнергию",
        (r"электроэнерг", r"энерготариф", r"оптовый рынок электро"),
    ),
)

INDUSTRIES: tuple[Industry, ...] = (
    Industry("Нефтегаз", (r"\bнефт", r"газпром", r"\bспг\b", r"нефтехим")),
    Industry("Металлургия", (r"сталь", r"металлург", r"никел", r"алюмини", r"\bруд[аыуе]\b")),
    Industry("Агросектор", (r"пшениц", r"\bзерн", r"урожа", r"агро", r"удобрен")),
    Industry("Ритейл", (r"ритейл", r"розничн", r"\bмагазин")),
    Industry("Строительство", (r"строител", r"девелопер", r"цемент")),
    Industry("Транспорт", (r"\bржд\b", r"авиакомпан", r"контейнер", r"фрахт")),
    Industry("Химия", (r"химическ", r"полимер", r"удобрен")),
    Industry("Энергетика", (r"электроэнерг", r"энергосбыт")),
    Industry("Машиностроение", (r"машиностроен", r"автопром")),
    Industry("Банки", (r"банковск\w+\s+сектор", r"\bсбер(?:банк)?\b", r"\bвтб\b")),
    Industry("Телеком", (r"телеком", r"сотов")),
    Industry("Пищевая промышленность", (r"пищев", r"молочн", r"мясопереработ")),
)

_TOPIC_PATTERNS = tuple(
    (topic, tuple(re.compile(pattern, re.IGNORECASE) for pattern in topic.patterns))
    for topic in TOPICS
)
_INDUSTRY_PATTERNS = tuple(
    (industry, tuple(re.compile(pattern, re.IGNORECASE) for pattern in industry.patterns))
    for industry in INDUSTRIES
)
_MAX_LABELS = 3


def classify(
    title: str,
    text: str = "",
    hinted: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    blob = f"{title}\n{text}"
    hinted_labels = list(dict.fromkeys(hinted or []))
    topics = _rank(_TOPIC_PATTERNS, blob, hinted_labels)
    industries = _rank(_INDUSTRY_PATTERNS, blob, [])
    return topics, industries


def _rank(compiled, blob: str, hinted: list[str]) -> list[str]:
    scores: dict[str, int] = {label: 2 for label in hinted}
    for item, patterns in compiled:
        hits = sum(1 for pattern in patterns if pattern.search(blob))
        if hits:
            scores[item.label] = scores.get(item.label, 0) + hits
    ordered = sorted(scores, key=lambda label: (-scores[label], label))
    return [label for label in ordered if scores[label] > 0][:_MAX_LABELS]
