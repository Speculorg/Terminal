from __future__ import annotations
import hashlib, json
from typing import Any, Tuple, Dict
from .model import ConfigModel
from .loader_env import load_model

class Configs:
    """
    Типобезопасный фасад.
    Автозагрузка: читаем configs.env, затем накладываем переменные окружения контейнера.
    Доступ к секциям только атрибутами.
    """
    def __init__(self) -> None:
        model, merged = load_model()
        self._m: ConfigModel = model
        self._hash: str = self._calc_hash(merged)

    # --- Секции ---
    @property
    def global_(self): return self._m.global_

    @property
    def context(self): return self._m.context

    @property
    def consul(self): return self._m.consul

    @property
    def vault(self): return self._m.vault

    @property
    def traefik(self): return self._m.traefik

    @property
    def logging(self): return self._m.logging

    @property
    def metrics(self): return self._m.metrics

    @property
    def fs(self): return self._m.fs

    @property
    def tls(self): return self._m.tls

    @property
    def kv(self): return self._m.kv

    @property
    def fsm(self): return self._m.fsm

    @property
    def registrar(self): return self._m.registrar

    # --- Удобные алиасы ---
    @property
    def version(self) -> str:
        return self._m.global_.version

    @property
    def domain_root(self) -> str:
        return self._m.global_.domain_root

    @property
    def config_hash(self) -> str:
        return self._hash

    # --- helpers ---
    def _calc_hash(self, merged_env: Dict[str, Any]) -> str:
        allow_prefixes = (
            "GLOBAL_", "SERVICE_", "CONSUL_", "VAULT_", "TRAEFIK_",
            "LOGGING_", "METRICS_", "FS_", "TLS_", "KV_", "FSM_", "REGISTRAR_", "CONFIGS_ENV_PATH"
        )
        filtered = {k: str(v) for k, v in merged_env.items() if any(k.startswith(p) for p in allow_prefixes)}
        raw = json.dumps(filtered, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
