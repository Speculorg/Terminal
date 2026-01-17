from __future__ import annotations
from typing import Any, Mapping, Optional

from _entities import EventCodeEnum, LogLevelEnum
from _interfaces import ILogger


class BaseLogger(ILogger):
    """
    Structured logger: базовые методы уровней поверх event().
    
    """

    def event(
        self,
        code: EventCodeEnum | str,
        *,
        level: LogLevelEnum | str = LogLevelEnum.INFO,
        message: Optional[str] = None,
        fields: Optional[Mapping[str, Any]] = None,
    ) -> None:
        raise NotImplementedError

    def debug(self, message: str, *, fields: Optional[Mapping[str, Any]] = None) -> None:
        self.event("log.debug", level=LogLevelEnum.DEBUG, message=message, fields=fields)

    def info(self, message: str, *, fields: Optional[Mapping[str, Any]] = None) -> None:
        self.event("log.info", level=LogLevelEnum.INFO, message=message, fields=fields)

    def warn(self, message: str, *, fields: Optional[Mapping[str, Any]] = None) -> None:
        self.event("log.warn", level=LogLevelEnum.WARN, message=message, fields=fields)

    def error(self, message: str, *, fields: Optional[Mapping[str, Any]] = None) -> None:
        self.event("log.error", level=LogLevelEnum.ERROR, message=message, fields=fields)
