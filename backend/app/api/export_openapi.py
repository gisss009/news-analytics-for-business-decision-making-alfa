"""Выгрузка схемы OpenAPI в файл (для генерации типизированного клиента фронтенда без запуска сервера).

Запуск: python -m app.api.export_openapi ../frontend/openapi.json
"""
import json
import sys
from pathlib import Path

from app.api.main import app

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    out.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("записано:", out)
