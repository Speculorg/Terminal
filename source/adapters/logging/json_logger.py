from __future__ import annotations
import json
import sys
import time
import threading
from typing import Optional, Mapping, Any, Dict, Tuple
from interfaces import ILogger, IConfigs
from entities import LogLevelEnum
from core.logging import LogContext

_WARN_FLOOD_WINDOW_SEC = 60

_LEVEL_ORDER = {
    LogLevelEnum.DEBUG.value: 10,
    LogLevelEnum.INFO.value: 20,
    LogLevelEnum.WARN.value: 30,
    LogLevelEnum.ERROR.value: 40,
}

def _ts_ms() -> int:
    return int(time.time() * 1000)

def _safe_write_json(obj: Dict[str, Any]) -> None:
    try:
        json.dump(obj, sys.stdout, ensure_ascii=False, separators=(",", ":"))
        sys.stdout.write("\n")
        sys.stdout.flush()
    except Exception:
        pass

def _extract_error_code(record: Mapping[str, Any]) -> Optional[str]:
    err = record.get("error")
    if isinstance(err, dict):
        code = err.get("code")
        if isinstance(code, str):
            return code
    return None

class JsonLogger(ILogger):
    """Простой JSON-логгер.
    Схема: timestamp, level, svc, state, correlation_id, event, details?, error?
    Без trace_id. Анти-флуд WARN: окно {} сек.
    """.format(_WARN_FLOOD_WINDOW_SEC)

    def __init__(self, cfg: IConfigs) -> None:
        self._cfg = cfg
        self._level = str(getattr(cfg.logging, "level", "INFO")).upper()
        self._min_order = _LEVEL_ORDER.get(self._level, 20)
        self._lock = threading.Lock()
        self._last_warn: Dict[Tuple[str, Optional[str], Optional[str]], float] = {}

    def _enabled(self, level: LogLevelEnum) -> bool:
        return _LEVEL_ORDER[level.value] >= self._min_order

    def log(self, level: LogLevelEnum, message: str, *, svc: Optional[str]=None, state: Optional[str]=None, event: Optional[str]=None, details: Optional[Mapping[str, Any]]=None) -> None:
        if not self._enabled(level):
            return
        ctx = LogContext.make(self._cfg, state=state)
        record: Dict[str, Any] = {
            "timestamp": _ts_ms(),
            "level": level.value,
            "svc": svc or ctx.svc,
            "state": state or ctx.state,
            "correlation_id": ctx.correlation_id,
            "event": (event if event is not None else message),
        }
        if details is not None:
            record["details"] = details
        # error не формируем здесь. Фасад может передать в details/error при необходимости.

        if level == LogLevelEnum.WARN:
            if not self._warn_ok(record.get("svc",""), record.get("event"), _extract_error_code(record)):
                return
        _safe_write_json(record)

    def debug(self, message: str, **kw) -> None:
        self.log(LogLevelEnum.DEBUG, message, **kw)

    def info(self, message: str, **kw) -> None:
        self.log(LogLevelEnum.INFO, message, **kw)

    def warn(self, message: str, **kw) -> None:
        self.log(LogLevelEnum.WARN, message, **kw)

    def error(self, message: str, **kw) -> None:
        self.log(LogLevelEnum.ERROR, message, **kw)

    def _warn_ok(self, svc: str, event: Optional[str], err_code: Optional[str]) -> bool:
        key = (svc, event, err_code)
        now = time.time()
        with self._lock:
            last = self._last_warn.get(key, 0.0)
            if now - last < _WARN_FLOOD_WINDOW_SEC:
                return False
            self._last_warn[key] = now
        return True
