from __future__ import annotations

from typing import Any, Mapping, Optional

from core._base import BaseLogger
from core._entities import EventCodeEnum, LogLevelEnum
from core._interfaces import IConfigs, ILogger

from core.logger.adapters.json_logger import JsonLogger


def _clean_level(raw: str) -> str:
    s = (raw or "").strip()
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        s = s[1:-1].strip()
    s = s.upper()
    if s in ("DEBUG", "INFO", "WARN", "WARNING", "ERROR"):
        return "WARN" if s == "WARNING" else s
    return "INFO"


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
        raw_level = str(cfg.get("LOGGING_LEVEL", "INFO"))
        level = _clean_level(raw_level)
        service = str(getattr(cfg, "service_name", "unknown"))

        impl = JsonLogger(service=service, level=level)
        log = cls(impl=impl)

        # Однократная диагностика: что реально применилось.
        # Помогает ловить случаи, когда env перекрыт или пришёл "кривым".
        log.event(
            "logging.level",
            level="INFO",
            fields={"svc": service, "raw": raw_level, "effective": level},
        )
        return log

    def event(
        self,
        code: EventCodeEnum | str,
        *,
        level: LogLevelEnum | str = LogLevelEnum.INFO,
        message: Optional[str] = None,
        fields: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self._impl.event(code, level=level, message=message, fields=fields)