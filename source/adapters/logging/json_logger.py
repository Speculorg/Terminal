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

class JsonLogger(ILogger):
    def __init__(self, cfg: IConfigs) -> None:
        self._cfg = cfg
        self._lock = threading.Lock()
        self._last_warn: Dict[Tuple[str, Optional[str], Optional[str]], float] = {}

    def log(self, level: LogLevelEnum, message: str, *, svc: Optional[str] = None,
            state: Optional[str] = None, event: Optional[str] = None,
            details: Optional[Mapping[str, Any]] = None) -> None:
        ctx = LogContext.build(self._cfg, state=state)
        record = {
            "timestamp": _utc_rfc3339(),
            "level": level.value,
            "svc": svc or ctx.svc,
            "state": state,
            "event": event,
            "correlation_id": ctx.correlation_id,
            "trace_id": ctx.trace_id,
            "message": message,
            "details": details if details is not None else None,
            "deadline_ms": None,
            "retry": None,
            "error": None,
        }
        if level == LogLevelEnum.WARN:
            if not self._warn_ok(record["svc"], record["event"], _extract_error_code(record)):
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
            if len(self._last_warn) > 1024:
                cutoff = now - _WARN_FLOOD_WINDOW_SEC
                self._last_warn = {k: t for k, t in self._last_warn.items() if t >= cutoff}
            return True

def _utc_rfc3339() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def _safe_write_json(obj: Mapping[str, Any]) -> None:
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
