from __future__ import annotations
from typing import Optional, Dict
from interfaces import IKV
from .paths import KVPaths

class StatesStore:
    """Операции с kv/states/<svc>. Запись только через CAS."""
    def __init__(self, kv: IKV, svc: str) -> None:
        self._kv = kv
        self._svc = svc
        self._paths = KVPaths()

    def read(self) -> tuple[int, Optional[Dict]]:
        key = self._paths.states_key(self._svc)
        return self._kv.read_json(key)

    def cas(self, payload: Dict, modify_index: int) -> bool:
        key = self._paths.states_key(self._svc)
        return self._kv.cas_json(key, payload, modify_index=modify_index)
