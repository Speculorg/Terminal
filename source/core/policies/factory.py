from __future__ import annotations
from dataclasses import dataclass
from .marker_policy import MarkerPolicy
from .fsm_policy import FSMPolicy
from .tls_policy import TLSPolicy
from .registrar_policy import RegistrarPolicy
from .health_policy import HealthPolicy
from .kv_policy import KVPolicy
from .fs_policy import FSPolicy
from typing import Any

@dataclass
class PoliciesFactory:
    cfg: object
    logger: Any
    registrar: Any
    kv: Any
    metrics: Any
    markers: Any
    fs: Any  # FS facade

    def __post_init__(self):
        self.marker = MarkerPolicy(self.cfg)
        self.fsm = FSMPolicy(self.cfg)
        self.tls = TLSPolicy(self.cfg)
        self.registrar = RegistrarPolicy(self.cfg, self.logger, self.registrar)
        self.health = HealthPolicy(self.cfg)
        self.kv = KVPolicy(self.cfg)
        self.fs_policy = FSPolicy(self.cfg, self.logger, self.metrics, self.fs)
