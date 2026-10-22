"""Настройки приложения из переменных окружения (.env в корне репозитория)."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTING_PATH = Path(__file__).resolve().parent / "model_routing.yaml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    # stub: детерминированные ответы без сети и ключа (по умолчанию); real: HTTP к OpenAI-совместимому API
    llm_mode: Literal["stub", "real"] = "stub"
    llm_base_url: str = "http://localhost:0/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_s: float = 60.0
    llm_max_retries: int = 3

    daily_budget_rub: float = 500.0
    budget_warn_ratio: float = 0.8

    data_dir: Path = REPO_ROOT / "data"
    db_path: Path = REPO_ROOT / "data" / "runtime" / "app.sqlite"

    max_verify_iterations: int = 2
    log_level: str = "INFO"


settings = Settings()


@lru_cache
def model_routing() -> dict:
    """Содержимое model_routing.yaml: шаг → модель, цены, идентификаторы у провайдера."""
    return yaml.safe_load(ROUTING_PATH.read_text(encoding="utf-8"))
