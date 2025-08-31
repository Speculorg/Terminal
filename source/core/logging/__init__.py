from __future__ import annotations

from typing import Any

from .base import Logger
from .json_logger import JsonLogger


def get_logger(service: str | None = None, **default_fields: Any) -> Logger:
    """Create a JSON logger bound to optional service name and default fields."""
    return JsonLogger(service=service, **default_fields)


__all__ = ["Logger", "get_logger"]
