from __future__ import annotations
from typing import Any, Mapping

from _interfaces import IConfigs


class BaseConfigs(IConfigs):
    """
    Базовый каркас конфигурации.
    
    """

    def as_dict(self) -> Mapping[str, Any]:
        raise NotImplementedError

    def get(self, key: str, default: Any = None) -> Any:
        raise NotImplementedError

    @property
    def service_name(self) -> str:
        raise NotImplementedError