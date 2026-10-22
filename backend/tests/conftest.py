import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Каждый тест работает со своей SQLite-БД и в режиме LLM stub."""
    monkeypatch.setattr(settings, "db_path", tmp_path / "test.sqlite")
    monkeypatch.setattr(settings, "llm_mode", "stub")
    yield settings.db_path


@pytest.fixture
def demo_db(tmp_path):
    """Полная демо-база: синтетика + офлайн-конвейер контента."""
    from app.data.loader import load_all
    from app.data.synthetic import generate
    from app.ingest import offline
    generate(42, tmp_path / "synthetic")
    load_all(tmp_path / "synthetic", "synthetic")
    offline.run()
