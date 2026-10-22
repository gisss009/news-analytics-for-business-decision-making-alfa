"""Скачивает датасет кейса в data/raw/ и материалы аналитики банка в data/analytics/ (оба в git не попадают).

Ссылки на папки Google Drive берутся из .env: DATASET_FOLDER_URL, ANALYTICS_FOLDER_URL.
Нужен gdown: pip install -r backend/requirements-dev.txt
Запуск: python scripts/fetch_data.py
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = {"DATASET_FOLDER_URL": (ROOT / "data" / "raw", "*.csv", 3),
           "ANALYTICS_FOLDER_URL": (ROOT / "data" / "analytics", "*.pdf", 9)}


def read_env() -> dict[str, str]:
    env = dict(os.environ)
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    return env


def main() -> int:
    try:
        import gdown
    except ImportError:
        print("Нет gdown: pip install -r backend/requirements-dev.txt")
        return 1
    env, failed = read_env(), []
    for var, (out, pattern, expected) in TARGETS.items():
        url = env.get(var)
        if not url:
            print(f"{var} не задан в .env, пропуск")
            failed.append(var)
            continue
        out.mkdir(parents=True, exist_ok=True)
        for attempt in range(1, 5):  # Drive часто рвёт SSL-соединение: повторяем, уже скачанное не трогаем
            try:
                gdown.download_folder(url, output=str(out), quiet=True, resume=True)
            except Exception as e:  # noqa: BLE001
                print(f"{var}: попытка {attempt} не удалась: {e}")
            if len(list(out.glob(pattern))) >= expected:
                break
            time.sleep(2 * attempt)
        got = sorted(p.name for p in out.glob(pattern))
        print(f"{out.relative_to(ROOT)}: {len(got)} файлов ({', '.join(got)})")
        if len(got) < expected:
            failed.append(var)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
