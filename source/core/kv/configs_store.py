from __future__ import annotations
from typing import Optional, Dict, Tuple
from interfaces.i_kv import IKV
from .paths import KVPaths

class ConfigsStore:
    """Read-only доступ к kv/configs/* в рантайме."""
    def __init__(self, kv: IKV, svc: str) -> None:
        self._kv = kv
        self._svc = svc
        self._paths = KVPaths()

    def read_global(self, name: str) -> tuple[int, Optional[Dict]]:
        return self._kv.read_json(self._paths.configs_global_key(name))

    def read_service(self, name: str) -> tuple[int, Optional[Dict]]:
        return self._kv.read_json(self._paths.configs_svc_key(self._svc, name))
