# source\core\runtime\status.py


from __future__ import annotations
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Tuple

class ServiceStatus(str, Enum):
    BOOTSTRAPPING = "BOOTSTRAPPING"
    INITIALIZING  = "INITIALIZING"
    SECURING      = "SECURING"
    TLS_TRANSITION= "TLS_TRANSITION"
    REGISTERING   = "REGISTERING"
    RUNNING       = "RUNNING"
    PAUSED        = "PAUSED"
    DEGRADED      = "DEGRADED"
    STOPPING      = "STOPPING"
    ERROR         = "ERROR"

@dataclass(slots=True)
class HealthSnapshot:
    state: str = "init"                      # up|down|degraded|init
    status: ServiceStatus = ServiceStatus.BOOTSTRAPPING
    tls_active: bool = False
    started_at: float = field(default_factory=lambda: time.time())
    phase: str = "BOOTSTRAPPING"
    reasons: Tuple[str, ...] = tuple()

    def to_dict(self) -> Dict[str, object]:
        return {
            "state": self.state,
            "status": self.status.value,
            "tls_active": self.tls_active,
            "started_at": self.started_at,
            "phase": self.phase,
            "reasons": list(self.reasons),
        }
