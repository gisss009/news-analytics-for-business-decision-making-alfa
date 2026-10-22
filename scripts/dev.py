"""Одна команда для демо: данные → backend (uvicorn :8000) → frontend (Vite в Docker :5173).

  python scripts/dev.py              # демо без ключа LLM (LLM_MODE=stub)
  python scripts/dev.py --no-browser # не открывать браузер
  python scripts/dev.py --real       # режим real: нужен LLM_API_KEY в .env

Требования: Python 3.11+ и запущенный Docker Desktop (Node ставить не нужно, он работает в контейнере node:24-slim).
При первом запуске создаётся backend/.venv и ставятся зависимости. Остановка — Ctrl+C.
"""
import argparse
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
BACKEND = ROOT / "backend"
VENV_PY = BACKEND / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
CONTAINER = "news-analytics-frontend"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from node import IMAGE, NODE_MODULES_VOLUME  # noqa: E402


def say(msg: str) -> None:
    print(f"[dev] {msg}", flush=True)


def ensure_venv() -> None:
    if VENV_PY.exists():
        return
    say("создаю backend/.venv и ставлю зависимости (один раз)…")
    venv.EnvBuilder(with_pip=True).create(BACKEND / ".venv")
    subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "-q", "-r", str(BACKEND / "requirements.txt")])


def run_py(env: dict, *args: str) -> None:
    subprocess.check_call([str(VENV_PY), "-X", "utf8", *args], cwd=BACKEND, env=env, stdout=subprocess.DEVNULL)


def ensure_docker() -> None:
    if not shutil.which("docker"):
        sys.exit("[dev] Docker не найден. Установите и запустите Docker Desktop.")
    if subprocess.call(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        sys.exit("[dev] Docker не отвечает. Запустите Docker Desktop и дождитесь статуса Running.")


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
    for stream in (sys.stdout, sys.stderr):  # вывод в UTF-8 и при перенаправлении в файл на Windows
        stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--real", action="store_true", help="LLM_MODE=real (по умолчанию stub)")
    a = ap.parse_args()

    ensure_docker()
    ensure_venv()
    env = {**os.environ, "LLM_MODE": "real" if a.real else "stub", "PYTHONUTF8": "1"}

    say("готовлю данные: синтетические компании и офлайн-набор новостей…")
    run_py(env, "-m", "app.data.loader", "--source", "synthetic")
    run_py(env, "-m", "app.ingest.offline")

    say("запускаю backend на http://127.0.0.1:8000 …")
    backend = subprocess.Popen([str(VENV_PY), "-m", "uvicorn", "app.api.main:app", "--host", "127.0.0.1",
                                "--port", "8000"], cwd=BACKEND, env=env)
    subprocess.call(["docker", "rm", "-f", CONTAINER], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    say("запускаю frontend в Docker на http://localhost:5173 (первый запуск ставит npm-зависимости)…")
    frontend = subprocess.Popen([
        "docker", "run", "--rm", "--name", CONTAINER, "-p", "5173:5173",
        "-e", "VITE_PROXY_TARGET=http://host.docker.internal:8000", "-e", "VITE_POLL=1",
        "-v", f"{ROOT / 'frontend'}:/app", "-v", f"{NODE_MODULES_VOLUME}:/app/node_modules", "-w", "/app", IMAGE,
        "sh", "-c", "npm install --no-audit --no-fund --loglevel=error && npm run dev"])
    try:
        if not wait_http("http://127.0.0.1:8000/health", 60):
            say("backend не поднялся за 60 с — смотрите вывод выше")
            return 1
        if not wait_http("http://127.0.0.1:5173", 240):
            say("frontend не поднялся за 4 минуты — смотрите вывод выше")
            return 1
        say("готово: откройте http://localhost:5173  (остановка — Ctrl+C)")
        if not a.no_browser:
            webbrowser.open("http://localhost:5173")
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(1)
        return 1
    except KeyboardInterrupt:
        say("останавливаю…")
        return 0
    finally:
        subprocess.call(["docker", "stop", CONTAINER], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        backend.terminate()
        try:
            backend.wait(10)
        except subprocess.TimeoutExpired:
            backend.kill()


if __name__ == "__main__":
    sys.exit(main())
