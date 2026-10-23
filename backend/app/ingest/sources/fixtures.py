"""STUB: источник новостей из офлайн-фикстур (data/fixtures/news) вместо сбора из интернета.

Замена: класс настоящего источника (RSS/HTML) с тем же интерфейсом Source и регистрация в registry().
"""
from datetime import datetime

from app.ingest.fixtures import load_fixtures
from app.ingest.sources.base import Link, RawArticle, Source

FIXTURE_URL = "fixture://news/{id}"


class FixtureSource(Source):
    name = "fixtures"

    def __init__(self, include_holdout: bool = True):
        self._items = {i.id: i for i in load_fixtures(include_holdout=include_holdout)}

    def fetch_list(self, since: datetime | None = None) -> list[Link]:
        return [Link(url=FIXTURE_URL.format(id=i.id), title=i.title, published_at=i.published_at)
                for i in self._items.values() if since is None or i.published_at > since]

    def fetch_article(self, link: Link) -> RawArticle:
        i = self._items[link.url.rsplit("/", 1)[-1]]
        return RawArticle(item_id=i.id, url=link.url, title=i.title, text=i.text, published_at=i.published_at,
                          source_name=i.source.name, source_type=i.source.type, synthetic=True, holdout=i.holdout)


def registry() -> dict[str, type[Source]]:
    """Источники по имени. Новый источник = класс Source + строка здесь."""
    from app.ingest.sources.pyfinews_source import PyfinewsSource
    return {"fixtures": FixtureSource, "live": PyfinewsSource}
