from __future__ import annotations
from typing import Optional

from interfaces import IConfigs
from core.configs.model import Model

class BaseConfigs(IConfigs):
    """Базовый каркас фасада настроек.
    Реализует свойства доступа к моделям и базовую валидацию.
    """
    def __init__(self, model: Model) -> None:
        self._model = model
        self._validate()

    # --- секции ---
    @property
    def global_(self): return self._model.global_

    @property
    def context(self): return self._model.context

    @property
    def consul(self): return self._model.consul

    @property
    def vault(self): return self._model.vault

    @property
    def traefik(self): return self._model.traefik

    @property
    def logging(self): return self._model.logging

    @property
    def metrics(self): return self._model.metrics

    @property
    def fs(self): return self._model.fs

    @property
    def tls(self): return self._model.tls

    @property
    def kv(self): return self._model.kv

    @property
    def fsm(self): return self._model.fsm

    @property
    def registrar(self): return self._model.registrar

    # --- алиасы ---
    @property
    def version(self) -> str: return self._model.global_.version

    @property
    def domain_root(self) -> str: return self._model.global_.domain_root

    @property
    def config_hash(self) -> str: return self._model.config_hash

    # --- валидация ---
    def _validate(self) -> None:
        # Контекст
        name = self._model.context.name or ""
        if not isinstance(name, str) or not name:
            raise ValueError("cfg.context.name must be non-empty str")
        port = int(self._model.context.port)
        if port < 0 or port > 65535:
            raise ValueError("cfg.context.port must be 0..65535")
        if self._model.context.tags is None:
            raise ValueError("cfg.context.tags must be list[str]")

        # FSM тайминги: все неотрицательные
        fsm = self._model.fsm
        ints = [
            fsm.state_bootstrapping_timeout_ms,
            fsm.state_initializing_timeout_ms,
            fsm.state_securing_timeout_ms,
            fsm.state_tls_transition_timeout_ms,
            fsm.state_registering_timeout_ms,
            fsm.state_running_tick_timeout_ms,
            fsm.state_publish_min_interval_ms,
            fsm.degraded_recovery_window_ms,
            fsm.degraded_transition_window_ms,
            fsm.degraded_min_duration_ms,
        ]
        if any(int(x) < 0 for x in ints):
            raise ValueError("cfg.fsm timeouts must be >= 0")
