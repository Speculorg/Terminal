"""Минимальные исключения для fail-fast проверок (TERM-1: Stage 2)."""
from __future__ import annotations

class PreconditionError(RuntimeError):
    """Нарушение предусловий вызова."""

class OperationTimeoutError(TimeoutError):
    """Операция превысила лимит времени."""
