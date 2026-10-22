"""ОКВЭД → отрасль и чувствительность к макрофакторам. Правила в okved_map.yaml."""
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

MAP_PATH = Path(__file__).resolve().parent / "okved_map.yaml"
FACTORS = ("rate", "fx", "oil", "metals", "gold", "grain", "inflation", "demand", "regulation", "sanctions")


@dataclass(frozen=True)
class Sector:
    name: str
    title: str
    factors: dict[str, float]
    confidence: float
    matched_prefix: str | None = None
    keywords: tuple[str, ...] = field(default=())


@lru_cache
def load_map(path: Path = MAP_PATH) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    for name, s in data["sectors"].items():
        bad = set(s.get("factors", {})) - set(FACTORS)
        if bad:
            raise ValueError(f"okved_map: у отрасли {name} неизвестные факторы {sorted(bad)}")
    return data


def _sector(name: str, data: dict, confidence: float, prefix: str | None) -> Sector:
    s = data["sectors"][name]
    factors = {f: float(s.get("factors", {}).get(f, 0.0)) for f in FACTORS}
    return Sector(name, s["title"], factors, confidence, prefix, tuple(s.get("keywords", [])))


def sector_of(okved_code: str | None, path: Path = MAP_PATH) -> Sector:
    """Отрасль по самому длинному префиксу. Неизвестный или пустой код → 'other' с низкой уверенностью."""
    data = load_map(path)
    d = data["defaults"]
    code = (okved_code or "").strip()
    best: tuple[str, str] | None = None
    for name, s in data["sectors"].items():
        for p in s.get("prefixes", []):
            if (code == p or code.startswith(p + ".") or (len(p) > 2 and code.startswith(p))) and \
                    (best is None or len(p) > len(best[1])):
                best = (name, p)
    if best is None:
        return _sector(d["unknown_sector"], data, d["unknown_confidence"], None)
    conf = d["exact_confidence"] if len(best[1]) > 2 else d["group_confidence"]
    return _sector(best[0], data, conf, best[1])


def all_sectors(path: Path = MAP_PATH) -> list[Sector]:
    data = load_map(path)
    return [_sector(n, data, 1.0, None) for n in data["sectors"]]
