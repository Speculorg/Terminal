from __future__ import annotations
import hashlib, json
from typing import Any
from .model import ConfigModel
from .loader_env import load_model

class Configs:
    """
    Типобезопасный фасад.
    Автозагрузка: читаем configs.env, затем применяем переменные окружения контейнера.
    Доступ к секциям только атрибутами.
    """
    def __init__(self) -> None:
        model, merged = load_model()
        self._m: ConfigModel = model
        # Предрасчитанный хеш конфигурации для отладки и меток
        self._hash = self._calc_hash(merged)

    # Секции
    @property
    def global_(self):  # протокол ожидает global_
        return self._m.global_

    @property
    def context(self):
        return self._m.context

    @property
    def consul(self):
        return self._m.consul

    @property
    def vault(self):
        return self._m.vault

    @property
    def traefik(self):
        return self._m.traefik

    @property
    def logging(self):
        return self._m.logging

    @property
    def metrics(self):
        return self._m.metrics

    @property
    def fs(self):
        return self._m.fs

    @property
    def tls(self):
        return self._m.tls

    @property
    def kv(self):
        return self._m.kv

    @property
    def fsm(self):
        return self._m.fsm

    @property
    def registrar(self):
        return self._m.registrar

    # Удобные короткие алиасы, как просили
    @property
    def version(self) -> str:
        return self._m.global_.version

    @property
    def domain_root(self) -> str:
        return self._m.global_.domain_root

    @property
    def config_hash(self) -> str:
        return self._hash

    # helpers
    def _calc_hash(self, merged_env: dict[str, Any]) -> str:
        # Хешируем только ключи, которые начинаются с префиксов конфигураций
        allow = tuple([
            "GLOBAL_", "SERVICE_", "CONSUL_", "VAULT_", "TRAEFIK_",
            "LOGGING_", "METRICS_", "FS_", "TLS_", "KV_", "FSM_", "REGISTRAR_", "CONFIGS_ENV_PATH"
        ])
        filtered = {k: v for k, v in merged_env.items() if k.startswith(allow)}
        raw = json.dumps(filtered, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
