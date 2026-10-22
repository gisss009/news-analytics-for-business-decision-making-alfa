"""STUB: детерминированные ответы для LLM_MODE=stub.

Обработчик шага получает (messages, data), где data — содержимое последнего data_block() в промпте,
и возвращает dict (для JSON-ответа) или str. Шаги регистрируют свои шаблоны через register() в своих модулях.
Шаблонный ответ обязан соблюдать те же контракты, что и ответ модели (label и refs у каждого утверждения).
Замена на настоящую модель: LLM_MODE=real и ключ в .env; код шагов не меняется.
"""
from typing import Any, Callable

StubHandler = Callable[[list[dict], Any], dict | str]
_HANDLERS: dict[str, StubHandler] = {}


def register(step: str, handler: StubHandler) -> None:
    _HANDLERS[step] = handler


def get(step: str) -> StubHandler | None:
    return _HANDLERS.get(step)


def _echo(messages: list[dict], data: Any) -> str:
    return f"[stub] получено сообщений: {len(messages)}"


register("echo", _echo)
