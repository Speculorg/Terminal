from __future__ import annotations
import hashlib, json
from typing import Dict, Any, Iterable

class ConfigHasher:
    """Вычисляет config_hash по канону TERM-1."""
    _ALLOW_PREFIXES: tuple[str,...] = (
        "GLOBAL_", "SERVICE_", "CONSUL_", "VAULT_", "TRAEFIK_",
        "LOGGING_", "METRICS_", "FS_", "TLS_", "KV_", "FSM_",
        "REGISTRAR_", "CONFIGS_ENV_PATH"
    )

    @classmethod
    def calc(cls, merged_env: Dict[str, Any]) -> str:
        filtered = {k: str(v) for k, v in merged_env.items() if cls._allow(k)}
        raw = json.dumps(filtered, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @classmethod
    def _allow(cls, key: str) -> bool:
        return any(key.startswith(p) for p in cls._ALLOW_PREFIXES)
