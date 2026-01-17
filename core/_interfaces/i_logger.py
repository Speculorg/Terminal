from __future__ import annotations
from typing import Protocol, runtime_checkable, Any, Mapping, Optional
from _entities import EventCodeEnum, LogLevelEnum


@runtime_checkable
class ILogger(Protocol):
    """
    Structured logger: событие + поля.
    """

    def event(
        self,
        code: EventCodeEnum | str,
        *,
        level: LogLevelEnum | str = LogLevelEnum.INFO,
        message: Optional[str] = None,
        fields: Optional[Mapping[str, Any]] = None,
    ) -> None:
        ...

    def debug(self, message: str, *, fields: Optional[Mapping[str, Any]] = None) -> None: ...
    def info(self, message: str, *, fields: Optional[Mapping[str, Any]] = None) -> None: ...
    def warn(self, message: str, *, fields: Optional[Mapping[str, Any]] = None) -> None: ...
    def error(self, message: str, *, fields: Optional[Mapping[str, Any]] = None) -> None: ...
