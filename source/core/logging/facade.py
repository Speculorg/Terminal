from __future__ import annotations
from typing import Optional, Mapping, Any, Dict
from interfaces import IConfigs
from entities import LogLevelEnum
from base.base_logger import BaseLogger
from adapters.logging import JsonLogger

class Logger(BaseLogger):
    """Фасад логгера. Наследуется от BaseLogger и пишет в адаптер JsonLogger."""
    def __init__(self, cfg: IConfigs) -> None:
        super().__init__()
        self._sink = JsonLogger(cfg)

    def _write(self, rec: Dict[str, Any]) -> None:
        # Пробрасываем в JsonLogger с каноническими полями
        level = LogLevelEnum(rec.get("level"))
        event_code = rec.get("event") or ""
        svc = rec.get("svc")
        state = rec.get("state")
        details = rec.get("details")
        self._sink.log(level, event_code, svc=svc, state=state, event=event_code, details=details)
