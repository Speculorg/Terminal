from __future__ import annotations
from .model import Model

from interfaces import IConfigs


class Configs(IConfigs):
    """Единый фасад настроек. Принимает готовую модель.
    """
    def __init__(self, model: Model) -> None:
        self._model = model


    # Секции
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


    # Алиасы
    @property
    def version(self) -> str: return self._model.global_.version
    @property
    def domain_root(self) -> str: return self._model.global_.domain_root
    @property
    def config_hash(self) -> str: return self._model.config_hash
