from __future__ import annotations
from typing import Optional, Mapping, Any
from interfaces import ILogger, IConfigs

class Logger(ILogger):
    """Фасад логирования ядра. Делегирует в JsonLogger (adapter)."""
    def __init__(self, cfg: IConfigs) -> None:
        from adapters.logging import JsonLogger
        self._impl = JsonLogger(cfg)

    def debug(self, message: str, *, svc: Optional[str]=None, state: Optional[str]=None, event: Optional[str]=None, details: Optional[Mapping[str, Any]]=None) -> None:
        self._impl.debug(message, svc=svc, state=state, event=event, details=details)

    def info(self, message: str, *, svc: Optional[str]=None, state: Optional[str]=None, event: Optional[str]=None, details: Optional[Mapping[str, Any]]=None) -> None:
        self._impl.info(message, svc=svc, state=state, event=event, details=details)

    def warn(self, message: str, *, svc: Optional[str]=None, state: Optional[str]=None, event: Optional[str]=None, details: Optional[Mapping[str, Any]]=None) -> None:
        self._impl.warn(message, svc=svc, state=state, event=event, details=details)

    def error(self, message: str, *, svc: Optional[str]=None, state: Optional[str]=None, event: Optional[str]=None, details: Optional[Mapping[str, Any]]=None) -> None:
        self._impl.error(message, svc=svc, state=state, event=event, details=details)
