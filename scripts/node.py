"""Запуск npm/node фронтенда в Docker-контейнере node:24-slim (Node на машину не ставится).

Примеры:
  python scripts/node.py npm install
  python scripts/node.py npm run build
  python scripts/node.py npm run typecheck
Папка frontend/ монтируется в /app; node_modules лежат в именованном томе Docker (быстрее на Windows).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE = "node:24-slim"
NODE_MODULES_VOLUME = "news_analytics_frontend_node_modules"


def docker_cmd(args: list[str], ports: list[str] = (), env: dict[str, str] | None = None, tty: bool = False) -> list[str]:
    cmd = ["docker", "run", "--rm", "-v", f"{ROOT / 'frontend'}:/app", "-v", f"{NODE_MODULES_VOLUME}:/app/node_modules",
           "-w", "/app"]
    if tty:
        cmd.append("-t")
    for p in ports:
        cmd += ["-p", p]
    for k, v in (env or {}).items():
        cmd += ["-e", f"{k}={v}"]
    return cmd + [IMAGE] + args


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    return subprocess.call(docker_cmd(sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
