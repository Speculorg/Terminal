from __future__ import annotations

class KVPaths:
    """Справочник ключей KV."""
    def __init__(self, states_root: str = "kv/states", configs_root: str = "kv/configs") -> None:
        self._states_root = states_root.rstrip("/")
        self._configs_root = configs_root.rstrip("/")

    def states_key(self, svc: str) -> str:
        return f"{self._states_root}/{svc}"

    def configs_global_prefix(self) -> str:
        return f"{self._configs_root}/global"

    def configs_service_prefix(self, svc: str) -> str:
        return f"{self._configs_root}/{svc}"
