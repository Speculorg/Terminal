from __future__ import annotations
from interfaces import ILogger, IConfigs
from adapters.logging import JsonLogger

class Logger(ILogger):
    """Фасад логирования ядра. Делегирует в JsonLogger."""
    def __init__(self, cfg: IConfigs) -> None:
        self._impl = JsonLogger(cfg)

    # Делегаты
    def debug(self, message: str, *, svc: str|None=None, state: str|None=None, event: str|None=None, details: dict|None=None) -> None:
        self._impl.debug(message, svc=svc, state=state, event=event, details=details)

    def info(self, message: str, *, svc: str|None=None, state: str|None=None, event: str|None=None, details: dict|None=None) -> None:
        self._impl.info(message, svc=svc, state=state, event=event, details=details)

    def warn(self, message: str, *, svc: str|None=None, state: str|None=None, event: str|None=None, details: dict|None=None) -> None:
        self._impl.warn(message, svc=svc, state=state, event=event, details=details)

    def error(self, message: str, *, svc: str|None=None, state: str|None=None, event: str|None=None, details: dict|None=None) -> None:
        self._impl.error(message, svc=svc, state=state, event=event, details=details)
