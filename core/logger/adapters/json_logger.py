from __future__ import annotations

import json
import sys
import time
from typing import Any, Mapping, Optional

from _base import BaseLogger
from _entities import EventCodeEnum, LogLevelEnum


def _now_ms() -> int:
    return int(time.time() * 1000)


def _to_jsonable(value: Any) -> Any:
    """
    Безопасная нормализация значений для JSON.

    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    try:
        return str(value)
    except Exception:
        return "<unprintable>"


def _level_rank(level: str) -> int:
    m = {
        "DEBUG": 10,
        "INFO": 20,
        "WARN": 30,
        "WARNING": 30,
        "ERROR": 40,
    }
    return m.get(level.upper(), 20)


class JsonLogger(BaseLogger):
    """
    Structured JSON logger to stdout.

    Формат записи:
    {
      "ts_ms": 123,
      "svc": "svc-name",
      "level": "INFO",
      "code": "deps.build.ok",
      "msg": "...",
      "fields": {...}
    }
    
    """

    def __init__(self, *, service: str, level: str = "INFO") -> None:
        self._svc = service
        self._min_level = level.upper()

    def event(
        self,
        code: EventCodeEnum | str,
        *,
        level: LogLevelEnum | str = LogLevelEnum.INFO,
        message: Optional[str] = None,
        fields: Optional[Mapping[str, Any]] = None,
    ) -> None:
        try:
            lvl = str(level).upper()
            if _level_rank(lvl) < _level_rank(self._min_level):
                return

            rec = {
                "ts_ms": _now_ms(),
                "svc": self._svc,
                "level": lvl,
                "code": str(code),
            }
            if message:
                rec["msg"] = str(message)
            if fields:
                rec["fields"] = _to_jsonable(dict(fields))

            sys.stdout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception:
            # Логгер не должен валить процесс ни при каких условиях.
            try:
                sys.stdout.write('{"level":"ERROR","code":"logger.fail"}\n')
                sys.stdout.flush()
            except Exception:
                pass
