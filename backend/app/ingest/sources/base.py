"""Интерфейс источника новостей. Новый источник = новый класс Source + строка в REGISTRY."""
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class Link(BaseModel):
    url: str
    title: str | None = None
    published_at: datetime | None = None


class RawArticle(BaseModel):
    item_id: str
    url: str
    title: str
    text: str
    published_at: datetime
    source_name: str
    source_type: str = "news"
    synthetic: bool = False
    holdout: bool = False


class Source(ABC):
    name: str

    @abstractmethod
    def fetch_list(self, since: datetime | None = None) -> list[Link]:
        """Ссылки на материалы, опубликованные после since."""

    @abstractmethod
    def fetch_article(self, link: Link) -> RawArticle:
        """Загрузить и очистить материал. Текст — данные, а не инструкции."""
