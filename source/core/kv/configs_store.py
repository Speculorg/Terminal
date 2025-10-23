from __future__ import annotations
from typing import Optional, Dict
from interfaces import IKV
from .paths import KVPaths

class ConfigsStore:
    """Read-only доступ к kv/configs/* в рантайме."""
    def __init__(self, kv: IKV, svc: str) -> None:
        self._kv = kv
        self._svc = svc
        self._paths = KVPaths()

    def read_global(self, key: str) -> tuple[int, Optional[Dict]]:
        full = f"{self._paths.configs_global_prefix()}/{key}"
        return self._kv.read_json(full)

    def read_service(self, key: str) -> tuple[int, Optional[Dict]]:
        full = f"{self._paths.configs_service_prefix(self._svc)}/{key}"
        return self._kv.read_json(full)
