from __future__ import annotations
from dataclasses import dataclass


from .marker_policy import MarkerPolicy
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
        self.marker_policy = MarkerPolicy(self.cfg)
        self.tls_policy = TLSPolicy(self.cfg)
        self.registrar_policy = RegistrarPolicy(self.cfg, self.logger, self.registrar)
        self.health_policy = HealthPolicy(self.cfg)
        self.kv_policy = KVPolicy(self.cfg)
        self.fs_policy = FSPolicy(self.cfg, self.logger, self.metrics, self.fs)
