from __future__ import annotations
from interfaces import IKV, IConfigs
from .states_store import StatesStore
from .configs_store import ConfigsStore

class KV:
    """Единый фасад KV, привязанный к текущему svc из Configs."""
    def __init__(self, cfg: IConfigs, kv_impl: IKV) -> None:
        self._cfg = cfg
        self._impl = kv_impl
        svc = cfg.context.name
        self.states = StatesStore(kv_impl, svc)
        self.configs = ConfigsStore(kv_impl, svc)
