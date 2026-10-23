"""OCR PDF аналитики банка в Docker (Tesseract на машину не ставится).

  python scripts/ocr.py          # собрать образ при необходимости и распознать новые/изменённые PDF
  python scripts/ocr.py --force  # распознать все заново

PDF берутся из data/analytics/, результат — data/analytics/.ocr/<файл>.json (в git не попадает:
материалы банка нельзя распространять без разрешения).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE = "news-analytics-ocr:2"


def image_exists() -> bool:
    return subprocess.call(["docker", "image", "inspect", IMAGE], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) == 0


def main() -> int:
    if subprocess.call(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        print("[ocr] Docker не отвечает. Запустите Docker Desktop.")
        return 1
    if not list((ROOT / "data" / "analytics").glob("*.pdf")):
        print("[ocr] В data/analytics нет PDF. Скачайте материалы: python scripts/fetch_data.py")
        return 1
    if not image_exists():
        print("[ocr] собираю образ OCR (один раз, ~2 мин)…", flush=True)
        if subprocess.call(["docker", "build", "-t", IMAGE, str(ROOT / "docker" / "ocr")]) != 0:
            return 1
    print("[ocr] распознаю PDF…", flush=True)
    return subprocess.call(["docker", "run", "--rm", "-v", f"{ROOT / 'data' / 'analytics'}:/data", IMAGE, *sys.argv[1:]])


if __name__ == "__main__":
    sys.exit(main())
