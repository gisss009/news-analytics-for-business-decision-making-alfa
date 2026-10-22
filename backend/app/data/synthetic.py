"""Генератор синтетических данных в схеме датасета кейса (docs/data-dictionary.md).

Все записи вымышлены: идентификаторы с префиксами U_S / F_S / group_S, названия компаний помечены «(синтетика)».
Словари значений (формы собственности, стадии, градации, регионы, страны ВЭД) взяты из реального датасета,
строки реального датасета не копируются.

Состав: 10 «опорных» компаний для демо (известный профиль), ещё случайные крупные компании (выручка ≥ 15 млрд руб.),
контрагенты меньшего размера, физлица и граф платежей. Фиксированный seed даёт одинаковые файлы.

Запуск: python -m app.data.synthetic [--seed 42] [--out data/synthetic] [--stats]
"""
import argparse
import csv
import io
import random
from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.data.models import (COMPANIES_FILE, COMPANY_COLUMNS, CSV_DELIMITER, NAMES_FILE, PAYMENT_COLUMNS,
                             PAYMENTS_FILE, PERSON_COLUMNS, PERSONS_FILE)
from app.data.okved import sector_of

DEFAULT_SEED = 42

OKVED_POOL: list[tuple[str, str]] = [
    ("41.20", "Строительство жилых и нежилых зданий"),
    ("42.11", "Строительство автомобильных дорог и автомагистралей"),
    ("07.29.41", "Добыча руд и песков драгоценных металлов (золота, серебра и металлов платиновой группы)"),
    ("46.71", "Торговля оптовая твердым, жидким и газообразным топливом и подобными продуктами"),
    ("46.38", "Торговля оптовая прочими пищевыми продуктами, включая рыбу, ракообразных и моллюсков"),
    ("46.34", "Торговля оптовая напитками"),
    ("46.46", "Торговля оптовая фармацевтической продукцией"),
    ("46.72", "Торговля оптовая металлами и металлическими рудами"),
    ("46.51", "Торговля оптовая компьютерами, периферийными устройствами к компьютерам и программным обеспечением"),
    ("47.11", "Торговля розничная преимущественно пищевыми продуктами в неспециализированных магазинах"),
    ("47.71", "Торговля розничная одеждой в специализированных магазинах"),
    ("45.11", "Торговля легковыми автомобилями и грузовыми автомобилями малой грузоподъемности"),
    ("49.41", "Деятельность автомобильного грузового транспорта"),
    ("52.29", "Деятельность вспомогательная прочая, связанная с перевозками"),
    ("62.01", "Разработка компьютерного программного обеспечения"),
    ("01.11", "Выращивание зерновых (кроме риса), зернобобовых культур и семян масличных культур"),
    ("10.51", "Производство молока (кроме сырого) и молочной продукции"),
    ("24.10", "Производство чугуна, стали и ферросплавов"),
    ("06.10", "Добыча нефти"),
    ("35.14", "Торговля электроэнергией"),
    ("20.15", "Производство удобрений и азотных соединений"),
    ("68.20", "Аренда и управление собственным или арендованным недвижимым имуществом"),
    ("64.91", "Деятельность по финансовой аренде (лизингу/сублизингу)"),
    ("28.92", "Производство машин и оборудования для добычи полезных ископаемых и строительства"),
]
SMALL_OKVED_POOL: list[tuple[str, str]] = OKVED_POOL + [
    ("43.21", "Производство электромонтажных работ"),
    ("71.12", "Деятельность заказчика-застройщика, генерального подрядчика"),
    ("23.61", "Производство изделий из бетона для использования в строительстве"),
    ("25.11", "Производство строительных металлических конструкций, изделий и их частей"),
    ("70.22", "Консультирование по вопросам коммерческой деятельности и управления"),
    ("56.10", "Деятельность ресторанов и услуги по доставке продуктов питания"),
    ("33.12", "Ремонт машин и оборудования"),
]
OKFS = ["ЧАСТНАЯ СОБСТВЕННОСТЬ"] * 14 + ["СОВМЕСТНАЯ ЧАСТНАЯ И ИНОСТРАННАЯ СОБСТВЕННОСТЬ",
                                        "СОБСТВЕННОСТЬ ИНОСТРАННЫХ ЮРИДИЧЕСКИХ ЛИЦ", "ФЕДЕРАЛЬНАЯ СОБСТВЕННОСТЬ"]
AGES = ["0-3", "4-7", "8-15", "16-25"]
STAGES = ["Оптимизация", "Бизнес в новой реальности", "Рождение", "Стремительный рост", ""]
WORKERS = ["Менее 15", "16-100", "101-250", "Более 251"]
CL_TYPES = ["CLIENT", "CLIENT", "CLIENT", "CLOSE_CLIENT", "PROSPECT"]
COUNTRIES = ["КИТАЙ", "ТУРЦИЯ", "ОАЭ", "ИНДИЯ", "УЗБЕКИСТАН", "КАЗАХСТАН", "БЕЛАРУСЬ", "АРМЕНИЯ", "ГОНКОНГ"]
GEO = [  # (CITY, REGION, RC_NAME, CITY_NAME для физлиц)
    ("г. Москва", "Москва", "МОСКОВСКИЙ", "Москва"),
    ("г. Санкт-Петербург", "Санкт-Петербург", "Санкт-Петербург", "Санкт-Петербург"),
    ("г. Екатеринбург", "Свердловская область", "УРАЛЬСКИЙ", "Екатеринбург"),
    ("г. Новосибирск", "Новосибирская область", "СИБИРСКИЙ", "Новосибирск"),
    ("г. Казань", "Республика Татарстан", "ПОВОЛЖСКИЙ", "Казань"),
    ("г. Краснодар", "Краснодарский край", "ЮЖНЫЙ", "Краснодар"),
    ("г. Красноярск", "Красноярский край", "СИБИРСКИЙ", "Красноярск"),
    ("г. Владивосток", "Приморский край", "ДАЛЬНЕВОСТОЧНЫЙ", "Владивосток"),
    ("г. Челябинск", "Челябинская область", "УРАЛЬСКИЙ", "Челябинск"),
]
PRODUCT_COLS = ["CL_PRODUCT_RKO_MARK", "CL_PRODUCT_GAR_MARK", "CL_PRODUCT_LOA_MARK", "CL_PRODUCT_LEA_MARK",
                "CL_PRODUCT_DEP_MARK", "CL_PRODUCT_ZPP_MARK"]

# Опорные компании для демонстрации: (имя, ОКВЭД, выручка млрд, регион-индекс, продукты, ВЭД-страны, факторинг)
ANCHORS = [
    ("СтройИнвест Девелопмент", "41.20", 42, 0, {"RKO", "GAR", "LOA", "LEA", "ZPP"}, "", 0),
    ("Сибирское Золото", "07.29.41", 31, 6, {"RKO", "DEP", "ZPP"}, "КИТАЙ, ОАЭ", 0),
    ("ВолгаТопливо", "46.71", 27, 4, {"RKO", "LOA"}, "", 1),
    ("Продимпорт Восток", "46.38", 19, 7, {"RKO", "LOA", "GAR"}, "КИТАЙ, ТУРЦИЯ", 0),
    ("Северный Код", "62.01", 16, 1, {"RKO", "DEP", "ZPP"}, "", 0),
    ("Городской Ритейл", "47.11", 58, 0, {"RKO", "LEA", "ZPP", "LOA"}, "", 0),
    ("УралТрансЛогистик", "49.41", 17, 2, {"RKO", "LEA"}, "КАЗАХСТАН, УЗБЕКИСТАН", 0),
    ("МеталлТрейд Урал", "46.72", 24, 8, {"RKO", "LOA", "GAR"}, "КИТАЙ, ИНДИЯ, ТУРЦИЯ", 1),
    ("Кубань Агро", "01.11", 15.5, 5, {"RKO", "LOA", "LEA"}, "ТУРЦИЯ", 0),
    ("АвтоМир Импорт", "45.11", 35, 0, {"RKO", "LOA", "LEA", "GAR"}, "КИТАЙ", 0),
]
NAME_PARTS_A = ["Альфа", "Вектор", "Гранит", "Дельта", "Енисей", "Заря", "Импульс", "Каскад", "Лидер", "Магистраль",
                "Нева", "Олимп", "Прогресс", "Ресурс", "Сфера", "Терра", "Урал", "Феникс", "Эталон", "Ямал"]
NAME_PARTS_B = ["Групп", "Холдинг", "Трейд", "Инвест", "Пром", "Снаб", "Сервис", "Логистик", "Ресурс", "Технологии"]


def _f(x: float) -> str:
    return f"{float(x):.1f}"


def _flag(b: bool) -> str:
    return "1.0" if b else "0.0"


class _Gen:
    def __init__(self, seed: int):
        self.r = random.Random(seed)
        self.companies: list[dict] = []
        self.names: dict[str, str] = {}
        self.persons: list[dict] = []
        self.payments: dict[tuple[str, str], list[float]] = {}

    def company(self, uid: str, name: str, okved: tuple[str, str], revenue: float, geo: tuple, products: set[str],
                countries: str, factoring: bool, group: str, big: bool) -> dict:
        r = self.r
        row = {c: "" for c in COMPANY_COLUMNS}
        row.update(
            SYNTHETIC_U=uid, ORG_TYPE="КОММ_ОРГ", OKFS_NAME=r.choice(OKFS),
            COMPANY_AGE_YEARS_GRADATION=r.choice(AGES[1:] if big else AGES),
            ECO_MARK_LABEL=r.choice(STAGES), MAINOKVED_CODE=okved[0], MAINOKVED_NAME=okved[1],
            NEGATIVEMARK=_flag(r.random() < 0.08),
            AMOUNT_WORKERS_FNS_GRADATION="Более 251" if big else r.choice(WORKERS),
            AMOUNT_WORKERS_SPARK_GRADATION=("Более 251" if big else r.choice(WORKERS)) if r.random() < 0.15 else "",
            CL_TYPE=r.choice(CL_TYPES) if big else r.choice(CL_TYPES + ["PROSPECT"] * 3),
            FTS_FLAG=_flag(bool(countries)), FTS_COUNTRY_NAME=countries, FACTORING_MARK=_flag(factoring),
            REVENUE_COMPANY=_f(revenue), GROUP_ID=group, CITY=geo[0], REGION=geo[1],
        )
        for col in PRODUCT_COLS:
            row[col] = _flag(col.split("_")[2] in products)
        self.companies.append(row)
        self.names[uid] = f"{name} (синтетика)"
        return row

    def pay(self, beneficiary: str, payer: str, amount: float) -> None:
        amount = max(1000.0, round(amount / 1000) * 1000)
        cnt = max(1, int(amount / self.r.uniform(2e6, 2e7)))
        acc = self.payments.setdefault((beneficiary, payer), [0.0, 0])
        acc[0] += amount
        acc[1] += cnt


def generate(seed: int = DEFAULT_SEED, out_dir: Path | str | None = None, n_random_big: int = 25,
             n_small: int = 120, n_persons: int = 160) -> dict[str, Path]:
    """Пишет 3 CSV в схеме кейса и файл названий. Возвращает пути к файлам."""
    out = Path(out_dir or settings.data_dir / "synthetic")
    out.mkdir(parents=True, exist_ok=True)
    g = _Gen(seed)
    r = g.r
    okved_by_code = dict(SMALL_OKVED_POOL)

    big_ids: list[str] = []
    for i, (name, code, rev, geo_i, prods, countries, fact) in enumerate(ANCHORS, start=1):
        uid = f"U_S{i:04d}"
        g.company(uid, name, (code, okved_by_code[code]), rev * 1e9, GEO[geo_i], prods, countries, bool(fact),
                  f"group_S{i:03d}_sb", big=True)
        big_ids.append(uid)

    used_names = {a[0] for a in ANCHORS}
    for i in range(len(ANCHORS) + 1, len(ANCHORS) + n_random_big + 1):
        uid = f"U_S{i:04d}"
        name = f"{r.choice(NAME_PARTS_A)}{r.choice(NAME_PARTS_B)}"
        while name in used_names:
            name = f"{r.choice(NAME_PARTS_A)}{r.choice(NAME_PARTS_B)} {r.randint(2, 9)}"
        used_names.add(name)
        prods = {p for p in ("RKO", "GAR", "LOA", "LEA", "DEP", "ZPP") if r.random() < {"RKO": 0.9}.get(p, 0.35)}
        countries = ", ".join(sorted(r.sample(COUNTRIES, r.randint(1, 3)))) if r.random() < 0.35 else ""
        # каждая третья компания входит в группу одной из опорных компаний
        group = f"group_S{r.randint(1, len(ANCHORS)):03d}_sb" if r.random() < 0.33 else f"group_S{i:03d}_sb"
        g.company(uid, name, r.choice(OKVED_POOL), r.uniform(15.2, 120) * 1e9, r.choice(GEO), prods, countries,
                  r.random() < 0.1, group, big=True)
        big_ids.append(uid)

    small_ids: list[str] = []
    for j in range(1, n_small + 1):
        uid = f"U_S{1000 + j:04d}"
        prods = {p for p in ("RKO", "LOA", "LEA", "ZPP") if r.random() < 0.3}
        revenue = 1000.0 if r.random() < 0.03 else r.uniform(0.05, 9) * 1e9  # 1000 — как заглушка в реальных данных
        countries = r.choice(COUNTRIES) if r.random() < 0.15 else ""
        g.company(uid, f"Контрагент-{j:03d}", r.choice(SMALL_OKVED_POOL), revenue, r.choice(GEO), prods, countries,
                  False, f"group_S{1000 + j:04d}_sb", big=False)
        small_ids.append(uid)

    rev = {c["SYNTHETIC_U"]: float(c["REVENUE_COMPANY"]) for c in g.companies}
    for uid in big_ids:
        for sup in r.sample(small_ids, r.randint(4, 10)):  # поставщики: компания платит
            g.pay(sup, uid, rev[uid] * r.uniform(0.005, 0.06))
        for buyer in r.sample(small_ids, r.randint(2, 6)):  # покупатели: платят компании
            g.pay(uid, buyer, rev[buyer] * r.uniform(0.02, 0.2))
        if r.random() < 0.6:  # связи между крупными компаниями
            other = r.choice([b for b in big_ids if b != uid])
            g.pay(other, uid, rev[uid] * r.uniform(0.01, 0.05))
    # одна компания с высокой концентрацией: почти весь объём закупок у одного поставщика
    g.pay(small_ids[0], "U_S0004", rev["U_S0004"] * 0.35)
    groups: dict[str, list[str]] = {}
    for c in g.companies:
        groups.setdefault(c["GROUP_ID"], []).append(c["SYNTHETIC_U"])
    for members in groups.values():  # внутригрупповые платежи
        for a, b in zip(members, members[1:]):
            g.pay(a, b, min(rev[a], rev[b]) * r.uniform(0.01, 0.03))

    all_ids = big_ids + small_ids
    for k in range(1, n_persons + 1):
        uid = r.choice(big_ids) if k <= len(big_ids) * 2 else r.choice(all_ids)
        geo = next(gg for gg in GEO if gg[1] == next(c["REGION"] for c in g.companies if c["SYNTHETIC_U"] == uid))
        g.persons.append({"SYNTHETIC_F": f"F_S{k:04d}", "CITY_NAME": geo[3] if r.random() > 0.02 else "",
                          "RC_NAME": geo[2], "SYNTHETIC_U": uid})

    files = {
        COMPANIES_FILE: (list(COMPANY_COLUMNS), g.companies),
        PERSONS_FILE: (list(PERSON_COLUMNS), g.persons),
        PAYMENTS_FILE: (list(PAYMENT_COLUMNS), [
            {"BENEFICIARY": b, "PAYER": p, "PAY_AMT": _f(v[0]), "PAY_CNT": _f(v[1])}
            for (b, p), v in sorted(g.payments.items())]),
        NAMES_FILE: (["SYNTHETIC_U", "DISPLAY_NAME"],
                     [{"SYNTHETIC_U": k, "DISPLAY_NAME": v} for k, v in g.names.items()]),
    }
    paths = {}
    for fname, (header, rows) in files.items():
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=header, delimiter=CSV_DELIMITER, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        path = out / fname
        path.write_bytes(buf.getvalue().encode("utf-8"))
        paths[fname] = path
    return paths


def stats(source_dir: Path | str) -> dict:
    """Распределения для проверки, что синтетика не вырождена."""
    d = Path(source_dir)
    rows = list(csv.DictReader((d / COMPANIES_FILE).open(encoding="utf-8"), delimiter=CSV_DELIMITER))
    big = [c for c in rows if float(c["REVENUE_COMPANY"]) >= 15e9]
    pays = list(csv.DictReader((d / PAYMENTS_FILE).open(encoding="utf-8"), delimiter=CSV_DELIMITER))
    persons = list(csv.DictReader((d / PERSONS_FILE).open(encoding="utf-8"), delimiter=CSV_DELIMITER))
    return {
        "companies": len(rows),
        "big_companies": len(big),
        "big_sectors": dict(Counter(sector_of(c["MAINOKVED_CODE"]).name for c in big)),
        "big_okved_groups": len({c["MAINOKVED_CODE"][:2] for c in big}),
        "big_regions": len({c["REGION"] for c in big}),
        "big_products": {col: sum(c[col] == "1.0" for c in big) for col in PRODUCT_COLS + ["FTS_FLAG", "FACTORING_MARK"]},
        "groups_with_2plus": sum(1 for v in Counter(c["GROUP_ID"] for c in rows).values() if v > 1),
        "payments": len(pays),
        "persons": len(persons),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--stats", action="store_true", help="только напечатать статистику существующих файлов")
    a = p.parse_args()
    out = a.out or settings.data_dir / "synthetic"
    if not a.stats:
        for path in generate(a.seed, out).values():
            print("записано:", path)
    for k, v in stats(out).items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
