from __future__ import annotations

class KVPaths:
    """Канонические ключи KV согласно плану."""
    def states_key(self, svc: str) -> str:
        return f"kv/states/{svc}"

    def configs_global_key(self, name: str) -> str:
        return f"kv/configs/global/{name}"

    def configs_svc_key(self, svc: str, name: str) -> str:
        return f"kv/configs/{svc}/{name}"
