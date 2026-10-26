"""Одна команда для сводки web/: выгрузка парсера (data/out) → Vite в Docker на http://localhost:5174.

  python scripts/web.py               # собрать выгрузку, если её нет, и запустить сводку
  python scripts/web.py --refresh     # пересобрать выгрузку (свежие новости pyfinews + обзоры банка)
  python scripts/web.py --no-news     # выгрузка только из обзоров банка, без сети
  python scripts/web.py --no-browser  # не открывать браузер

Обзоры банка: PDF из data/analytics (python scripts/fetch_data.py) копируются в data/alfa, их текст берётся
из кэша OCR backend (data/analytics/.ocr, его делает scripts/ocr.py в Docker). Tesseract на машину не нужен.
Выгрузку делает парсер parser/ (без языковой модели); его зависимости ставятся в parser/.venv.

Требования: Python 3.11+ и запущенный Docker Desktop (Node работает в контейнере node:24-slim).
Сводка не использует backend и ключ LLM. Остановка — Ctrl+C.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANALYTICS = ROOT / "data" / "analytics"
ALFA = ROOT / "data" / "alfa"
OUT = ROOT / "data" / "out"
PARSER_VENV = ROOT / "parser" / ".venv"
PARSER_PY = PARSER_VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
CONTAINER = "news-analytics-web"
IMAGE = "node:24-slim"
NODE_MODULES_VOLUME = "news_analytics_web_node_modules"
PORT = 5174


def say(msg: str) -> None:
    print(f"[web] {msg}", flush=True)


def ensure_docker() -> None:
    if not shutil.which("docker"):
        sys.exit("[web] Docker не найден. Установите и запустите Docker Desktop.")
    if subprocess.call(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        sys.exit("[web] Docker не отвечает. Запустите Docker Desktop и дождитесь статуса Running.")


def ensure_parser_venv() -> None:
    if PARSER_PY.exists():
        return
    say("создаю parser/.venv и ставлю зависимости парсера (один раз)…")
    venv.EnvBuilder(with_pip=True).create(PARSER_VENV)
    subprocess.check_call([str(PARSER_PY), "-m", "pip", "install", "-q", "-r", str(ROOT / "requirements.txt")])


def prepare_bank_pdfs() -> None:
    """PDF банка в data/alfa и кэш их текста в формате парсера (data/alfa/.ocr/<имя>.json)."""
    pdfs = sorted(ANALYTICS.glob("*.pdf"))
    if not pdfs and not list(ALFA.glob("*.pdf")):
        say("PDF банка нет: python scripts/fetch_data.py скачает их в data/analytics. Пока — только новости")
        return
    if pdfs and any(not (ANALYTICS / ".ocr" / f"{pdf.name}.json").exists() for pdf in pdfs):
        say("распознаю PDF банка в Docker (один раз, ~3 мин)…")
        subprocess.call([sys.executable, str(ROOT / "scripts" / "ocr.py")])
    ALFA.mkdir(parents=True, exist_ok=True)
    for pdf in pdfs:
        target = ALFA / pdf.name
        if not target.exists() or target.stat().st_size != pdf.stat().st_size:
            shutil.copy2(pdf, target)
        source = ANALYTICS / ".ocr" / f"{pdf.name}.json"
        if not source.exists():
            continue
        pages = json.loads(source.read_text(encoding="utf-8"))["pages"]
        stat = target.stat()
        cache = ALFA / ".ocr" / f"{target.stem}.json"
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(json.dumps({"size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
                                     "pages": [{"page": p["page"], "text": p["text"]} for p in pages]},
                                    ensure_ascii=False), encoding="utf-8")


def build_export(no_news: bool) -> None:
    ensure_parser_venv()
    prepare_bank_pdfs()
    env = {**os.environ, "PYTHONUTF8": "1"}
    say("собираю выгрузку " + ("из обзоров банка…" if no_news else "из обзоров банка и свежих новостей (~1–3 мин)…"))
    subprocess.check_call([str(PARSER_PY), "-m", "parser", *(["--no-news"] if no_news else [])], cwd=ROOT, env=env)
    if not no_news:
        subprocess.check_call([str(PARSER_PY), "-m", "parser._pull_business"], cwd=ROOT, env=env)


def wait_http(url: str, timeout: float) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except Exception:  # noqa: BLE001 — сервис ещё стартует
            time.sleep(1)
    return False


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="пересобрать выгрузку data/out")
    ap.add_argument("--no-news", action="store_true", help="только обзоры банка, без сети")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()

    ensure_docker()
    if a.refresh or a.no_news or not (OUT / "materials.json").exists():
        build_export(a.no_news)
    else:
        say("выгрузка data/out уже есть (пересобрать: --refresh)")

    subprocess.call(["docker", "rm", "-f", CONTAINER], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    say(f"запускаю сводку в Docker на http://localhost:{PORT} (первый запуск ставит npm-зависимости)…")
    server = subprocess.Popen([
        "docker", "run", "--rm", "--name", CONTAINER, "-p", f"{PORT}:{PORT}",
        "-v", f"{ROOT}:/repo", "-v", f"{NODE_MODULES_VOLUME}:/repo/web/node_modules", "-w", "/repo/web", IMAGE,
        "sh", "-c", f"npm install --no-audit --no-fund --loglevel=error && npx vite --host 0.0.0.0 --port {PORT}"])
    try:
        if not wait_http(f"http://127.0.0.1:{PORT}", 240):
            say("сводка не поднялась за 4 минуты — смотрите вывод выше")
            return 1
        say(f"готово: откройте http://localhost:{PORT}  (остановка — Ctrl+C)")
        if not a.no_browser:
            webbrowser.open(f"http://localhost:{PORT}")
        while server.poll() is None:
            time.sleep(1)
        return 1
    except KeyboardInterrupt:
        say("останавливаю…")
        return 0
    finally:
        subprocess.call(["docker", "stop", CONTAINER], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    sys.exit(main())
