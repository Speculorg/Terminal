from __future__ import annotations
from typing import Protocol, Any


class Logger(Protocol):
    """Basic logger interface for structured JSON logging with printf-style support."""

    def bind(self, **fields: Any) -> "Logger":
        """Return a new logger with additional context fields."""
        ...

    def debug(self, msg: str, *args: Any, **fields: Any) -> None:
        """Log a debug message. If args are provided, msg % args formatting is applied."""
        ...

    def info(self, msg: str, *args: Any, **fields: Any) -> None:
        """Log an info message. If args are provided, msg % args formatting is applied."""
        ...

    def warning(self, msg: str, *args: Any, **fields: Any) -> None:
        """Log a warning message. If args are provided, msg % args formatting is applied."""
        ...

    def error(self, msg: str, *args: Any, **fields: Any) -> None:
        """Log an error message. If args are provided, msg % args formatting is applied."""
        ...

    def exception(self, msg: str, *args: Any, **fields: Any) -> None:
        """Log an exception with traceback information. If args are provided, msg % args formatting is applied."""
        ...
