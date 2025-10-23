from __future__ import annotations
from typing import Optional
from .model import Model
from interfaces import IConfigs

class Configs(IConfigs):
    """Единый фасад настроек.
    Создаётся из готовой модели. Если модель не передана, загрузит через load_env().
    Хэш берётся из поля model.config_hash (заполняется в loader_env).
    """
    _instance: Optional["Configs"] = None

    def __init__(self, model: Model | None = None) -> None:
        if model is None:
            from .loader_env import load_env
            model = load_env()
        self._model: Model = model

    @classmethod
    def load(cls, env_file_path: str | None = None) -> "Configs":
        from .loader_env import load_env
        model = load_env(env_file_path)
        inst = cls(model)
        cls._instance = inst
        return inst

    @property
    def model(self) -> Model:
        return self._model

    @property
    def config_hash(self) -> str:
        return self.config_hash

    # Удобные прокси к секциям модели
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
    @property
    def config_hash(self): return self._model.config_hash
