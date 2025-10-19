from __future__ import annotations
from interfaces.i_kv import IKV
from .paths import KVPaths
from .states_store import StatesStore
from .configs_store import ConfigsStore

class KV:
    """Фасад KV. Не создаёт адаптер, принимает IKV извне (DI)."""
    def __init__(self, kv_impl: IKV, *, svc: str) -> None:
        self.paths = KVPaths()
        self.states = StatesStore(kv_impl, svc=svc)
        self.configs = ConfigsStore(kv_impl, svc=svc)
