from __future__ import annotations
from dataclasses import dataclass
from .marker_policy import MarkerPolicy
from .fsm_policy import FSMPolicy
from .tls_policy import TLSPolicy
from .registrar_policy import RegistrarPolicy
from .health_policy import HealthPolicy
from .kv_policy import KVPolicy

@dataclass
class PoliciesFactory:
    cfg: object

    def __post_init__(self):
        self.marker = MarkerPolicy(self.cfg)
        self.fsm = FSMPolicy(self.cfg)
        self.tls = TLSPolicy(self.cfg)
        self.registrar = RegistrarPolicy(self.cfg)
        self.health = HealthPolicy(self.cfg)
        self.kv = KVPolicy(self.cfg)
