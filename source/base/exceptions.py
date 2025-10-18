
"""Минимальные исключения для fail-fast проверок (TERM-1: Stage 2)."""
from __future__ import annotations

class PreconditionError(RuntimeError):
    """Нарушение предусловий вызова (например, отсутствует обязательный параметр deadline_ms)."""

class DeadlineRequiredError(PreconditionError):
    """Отсутствует именованный параметр deadline_ms в вызове метода."""

class OperationTimeoutError(TimeoutError):
    """Операция превысила дедлайн."""
