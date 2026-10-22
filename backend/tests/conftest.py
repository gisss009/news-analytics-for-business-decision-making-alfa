import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Каждый тест работает со своей SQLite-БД и в режиме LLM stub."""
    monkeypatch.setattr(settings, "db_path", tmp_path / "test.sqlite")
    monkeypatch.setattr(settings, "llm_mode", "stub")
    yield settings.db_path
