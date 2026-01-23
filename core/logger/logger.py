from __future__ import annotations

from typing import Any, Mapping, Optional

from core._base import BaseLogger
from core._entities import EventCodeEnum, LogLevelEnum
from core._interfaces import IConfigs, ILogger

from core.logger.adapters.json_logger import JsonLogger


class Logger(BaseLogger):
    """
    Logger — фасад логирования Core.

    TERM-1: по умолчанию JSON в stdout.
    В будущем можно добавить другие адаптеры (file/syslog/otel), но контракт останется.
    """

    def __init__(self, impl: ILogger) -> None:
        self._impl = impl

    @classmethod
    def from_configs(cls, *, cfg: IConfigs) -> "Logger":
        # TERM-1: минимальная маршрутизация по env/секциям
        level = str(cfg.get("LOGGING_LEVEL", "INFO"))
        service = str(getattr(cfg, "service_name", "unknown"))
        impl = JsonLogger(service=service, level=level)
        return cls(impl=impl)

    def event(
        self,
        code: EventCodeEnum | str,
        *,
        level: LogLevelEnum | str = LogLevelEnum.INFO,
        message: Optional[str] = None,
        fields: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self._impl.event(code, level=level, message=message, fields=fields)
