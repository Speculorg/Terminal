from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Mapping, Optional

from _entities import EventCodeEnum, LogLevelEnum
from _interfaces import ILogger


def _now_ms() -> int:
    return int(time.time() * 1000)


def _to_jsonable(value: Any) -> Any:
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
    m = {"DEBUG": 10, "INFO": 20, "WARN": 30, "WARNING": 30, "ERROR": 40}
    return m.get(level.upper(), 20)


class BaseLogger(ILogger):
    """
    Structured logger: базовые методы уровней поверх event().

    Принцип: базовый logger должен быть *рабочим по умолчанию*.
    Если конкретный адаптер не задан, event() пишет JSON в stdout.

    Это устраняет NotImplementedError и предотвращает “растекание логики” в сервисы.
    """

    def __init__(self, *, service: Optional[str] = None, level: str = "INFO") -> None:
        self._svc = service or os.getenv("SERVICE_NAME", "unknown")
        self._min_level = (level or "INFO").upper()

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

            rec: dict[str, Any] = {
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
            # Логгер никогда не должен валить процесс
            try:
                sys.stdout.write('{"level":"ERROR","code":"logger.fail"}\n')
                sys.stdout.flush()
            except Exception:
                pass

    def debug(self, message: str, *, fields: Optional[Mapping[str, Any]] = None) -> None:
        self.event("log.debug", level=LogLevelEnum.DEBUG, message=message, fields=fields)

    def info(self, message: str, *, fields: Optional[Mapping[str, Any]] = None) -> None:
        self.event("log.info", level=LogLevelEnum.INFO, message=message, fields=fields)

    def warn(self, message: str, *, fields: Optional[Mapping[str, Any]] = None) -> None:
        self.event("log.warn", level=LogLevelEnum.WARN, message=message, fields=fields)

    def error(self, message: str, *, fields: Optional[Mapping[str, Any]] = None) -> None:
        self.event("log.error", level=LogLevelEnum.ERROR, message=message, fields=fields)
