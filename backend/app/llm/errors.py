"""Исключения слоя LLM. Все, кроме ModelNotAllowed, означают: шаг должен уйти в запасной вариант."""


class ModelNotAllowed(ValueError):
    pass


class LLMError(RuntimeError):
    """Модель недоступна или ответ невалиден. Вызывающий шаг обязан иметь запасной вариант."""


class BudgetExceeded(LLMError):
    pass
