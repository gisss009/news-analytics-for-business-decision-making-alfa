"""Единственная точка доступа к LLM. Только 6 разрешённых моделей (docs/01-spec.md §3).

Режимы (LLM_MODE):
- stub (по умолчанию): детерминированный ответ обработчика из llm/stubs.py по шагу; сеть и ключ не нужны.
- real: OpenAI-совместимый HTTP (LLM_BASE_URL/chat/completions) с ретраями.

Внешние тексты (новости, документы) передаются в промпт только через data_block(): это данные, не инструкции.
"""
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import model_routing, settings
from app.core.logging import get_logger, log_tool_call

ALLOWED_MODELS = frozenset({
    "gemma-4-26b-a4b",            # простые задачи: классификация, извлечение
    "glm-5.3-flash",              # повышенная сложность, рассуждения
    "qwen3.6-35b-a3b",            # универсальная
    "deepseek-v4.1-flash",        # исследование, связи, большие объёмы
    "qwen3-vl-30b-a3b-instruct",  # изображения
    "kimi-k2.6",                  # обработка текста
})

RETRY_STATUS = {429, 500, 502, 503, 504}
DATA_OPEN, DATA_CLOSE = "<<<DATA", "DATA>>>"

T = TypeVar("T", bound=BaseModel)
log = get_logger("llm")

# Подменяются в тестах
_transport: httpx.BaseTransport | None = None
_sleep: Callable[[float], None] = time.sleep


class ModelNotAllowed(ValueError):
    pass


class LLMError(RuntimeError):
    """Модель недоступна или ответ невалиден. Вызывающий шаг обязан иметь запасной вариант."""


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def check_model(model: str) -> None:
    if model not in ALLOWED_MODELS:
        raise ModelNotAllowed(f"Модель '{model}' не входит в список разрешённых: {sorted(ALLOWED_MODELS)}")


def model_for(step: str) -> str:
    r = model_routing()
    model = r["steps"].get(step, r["default"])
    check_model(model)
    return model


def data_block(data: Any) -> str:
    """Оборачивает внешние данные в разделители. Модель получает инструкцию считать их только данными."""
    body = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    body = body.replace(DATA_OPEN, "").replace(DATA_CLOSE, "")  # данные не могут закрыть блок досрочно
    return f"{DATA_OPEN}\n{body}\n{DATA_CLOSE}"


def extract_data(messages: list[dict]) -> Any:
    """Последний блок данных из сообщений (для stub-обработчиков). JSON, если парсится, иначе строка."""
    pat = re.compile(re.escape(DATA_OPEN) + r"\n(.*?)\n" + re.escape(DATA_CLOSE), re.S)
    for m in reversed(messages):
        found = pat.findall(m.get("content", ""))
        if found:
            try:
                return json.loads(found[-1])
            except json.JSONDecodeError:
                return found[-1]
    return None


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def complete(step: str, messages: list[dict], schema: type[T] | None = None, temperature: float = 0.2,
             model: str | None = None) -> str | T:
    """Вызов модели для шага step. С schema возвращает валидированный объект Pydantic."""
    model = model or model_for(step)
    check_model(model)
    if settings.llm_mode == "stub":
        text, usage = _stub_call(step, messages)
        return _finish(step, model, messages, text, usage, schema, repair=None)
    text, usage = _http_call(model, messages, temperature, json_mode=schema is not None)
    repair = (lambda msgs: _http_call(model, msgs, temperature, json_mode=True)) if schema else None
    return _finish(step, model, messages, text, usage, schema, repair)


def _finish(step, model, messages, text, usage, schema, repair):
    ok = True
    try:
        if schema is None:
            return text
        try:
            return _parse(text, schema)
        except (ValidationError, ValueError) as e:
            if repair is None:
                raise LLMError(f"{step}: ответ не соответствует схеме {schema.__name__}: {e}") from e
            fix = messages + [
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"Ответ не прошёл проверку схемы: {str(e)[:500]}. "
                                            "Верни только валидный JSON по схеме, без пояснений."},
            ]
            text, usage2 = repair(fix)
            usage.prompt_tokens += usage2.prompt_tokens
            usage.completion_tokens += usage2.completion_tokens
            try:
                return _parse(text, schema)
            except (ValidationError, ValueError) as e2:
                raise LLMError(f"{step}: ответ невалиден и после исправления: {e2}") from e2
    except Exception:
        ok = False
        raise
    finally:
        log_tool_call(step, f"llm:{model}", {"mode": settings.llm_mode, "messages": len(messages),
                                             "chars": sum(len(m.get("content", "")) for m in messages)},
                      result=text, tokens=usage.total, ok=ok)


def _parse(text: str, schema: type[T]) -> T:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return schema.model_validate_json(cleaned)


def _stub_call(step: str, messages: list[dict]) -> tuple[str, Usage]:
    from app.llm import stubs
    handler = stubs.get(step)
    if handler is None:
        raise LLMError(f"{step}: в режиме stub нет обработчика; используйте запасной вариант шага")
    out = handler(messages, extract_data(messages))
    text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
    prompt = sum(estimate_tokens(m.get("content", "")) for m in messages)
    return text, Usage(prompt, estimate_tokens(text))


def _http_call(model: str, messages: list[dict], temperature: float, json_mode: bool) -> tuple[str, Usage]:
    key = settings.llm_api_key.get_secret_value()
    if not key:
        raise LLMError("LLM_MODE=real, но LLM_API_KEY не задан")
    provider_model = (model_routing().get("provider_ids") or {}).get(model, model)
    body: dict[str, Any] = {"model": provider_model, "messages": messages, "temperature": temperature}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    last_err: Exception | None = None
    with httpx.Client(timeout=settings.llm_timeout_s, transport=_transport) as http:
        for attempt in range(settings.llm_max_retries + 1):
            try:
                r = http.post(url, json=body, headers={"Authorization": f"Bearer {key}"})
                if r.status_code in RETRY_STATUS:
                    last_err = LLMError(f"HTTP {r.status_code}")
                else:
                    r.raise_for_status()
                    data = r.json()
                    u = data.get("usage") or {}
                    text = data["choices"][0]["message"]["content"]
                    return text, Usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
            except httpx.TransportError as e:
                last_err = e
            except (httpx.HTTPStatusError, KeyError, IndexError, ValueError) as e:
                raise LLMError(f"Ошибка ответа LLM: {e}") from e
            if attempt < settings.llm_max_retries:
                delay = 0.5 * 2 ** attempt
                log.warning("llm_retry", extra={"attempt": attempt + 1, "delay": delay, "error": str(last_err)})
                _sleep(delay)
    raise LLMError(f"LLM недоступна после {settings.llm_max_retries + 1} попыток: {last_err}")


if __name__ == "__main__":  # python -m app.llm.client echo "текст"
    import sys
    step, text = sys.argv[1], " ".join(sys.argv[2:])
    try:
        print(complete(step, [{"role": "user", "content": data_block(text)}]))
    except LLMError as e:
        print("LLMError:", e)
