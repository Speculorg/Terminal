from __future__ import annotations
from dataclasses import replace
from typing import Optional
from .model import Model
from .loader_env import load_model
from .hasher import config_hash

class Configs:
    _instance: Optional["Configs"] = None

    def __init__(self, model: Model):
        self._model = model
        self._hash = config_hash(model)

    @classmethod
    def load(cls, env_file_path: str | None = None) -> "Configs":
        model = load_model(env_file_path)
        inst = cls(model)
        cls._instance = inst
        return inst

    @property
    def model(self) -> Model:
        return self._model

    @property
    def hash(self) -> str:
        return self._hash

    # Проксируем секции как атрибуты фасада
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
