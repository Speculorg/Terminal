from __future__ import annotations
import json
import sys
from datetime import datetime
from typing import Optional

from core.logging import Logger, get_logger

__all__ = ["Logger", "get_logger", "make_logger"]

# Emit one-time migration warning on first import of this module
_warning_record = {
    "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
    "lvl": "WARN",
    "msg": "module.moved",
    "from": "core.observability.log",
    "to": "core.logging",
}
sys.stderr.write(json.dumps(_warning_record, ensure_ascii=False) + "\n")
sys.stderr.flush()


def make_logger(name: Optional[str] = None, level: Optional[str] = None) -> Logger:
    """
    Backward-compatible factory kept for legacy imports:
    - `name` maps to the new `service` field.
    - `level` is accepted for signature compatibility but ignored,
       because severity routing is handled per call (info/error/etc.).
    Returns a Logger implementing the new JSON logging interface.
    """
    return get_logger(service=name)
