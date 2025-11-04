from __future__ import annotations
from typing import Optional, Mapping, Any, Dict
from entities import LogLevelEnum
from interfaces import ILogger

class BaseLogger(ILogger):
    """Базовый каркас логгера.
    Стандартизирует схему записи: event-code вместо произвольного текста.
    Гарантирует наличие полей svc, state, details.
    """
    def __init__(self) -> None:
        super().__init__()  # type: ignore

    # --- публичные методы по протоколу ---
    def log(self, level: LogLevelEnum, message: str, *, svc: Optional[str] = None,
            state: Optional[str] = None, event: Optional[str] = None,
            details: Optional[Mapping[str, Any]] = None) -> None:
        rec = self._normalize(level, message, svc=svc, state=state, event=event, details=details)
        self._write(rec)

    def debug(self, message: str, **kw) -> None:
        self.log(LogLevelEnum.DEBUG, message, **kw)

    def info(self, message: str, **kw) -> None:
        self.log(LogLevelEnum.INFO, message, **kw)

    def warn(self, message: str, **kw) -> None:
        self.log(LogLevelEnum.WARN, message, **kw)

    def error(self, message: str, **kw) -> None:
        self.log(LogLevelEnum.ERROR, message, **kw)

    # --- нормализация и запись ---
    def _normalize(self, level: LogLevelEnum, message: str, *, svc: Optional[str],
                   state: Optional[str], event: Optional[str],
                   details: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
        event_code = event if event is not None else message
        rec: Dict[str, Any] = {
            "level": level.value,
            "event": event_code,
            "svc": svc,
            "state": state,
            "details": dict(details) if details is not None else None,
        }
        return rec

    def _write(self, rec: Dict[str, Any]) -> None:  # to be implemented by facade
        raise NotImplementedError
