
from __future__ import annotations
from dataclasses import dataclass, field
from base import BaseService
from interfaces import IRunProfile
from entities.state_enum import StateEnum

@dataclass(frozen=True)
class TraefikRunProfile(IRunProfile):
    required_markers: set[str] = field(default_factory=lambda: {'initial_pem.done'})
    stage_gates: dict = field(default_factory=lambda: {
        StateEnum.SECURING: [('consul','tokens'), ('certs','initial_pem')],
        StateEnum.REGISTERING: [('consul','tokens'), ('certs','initial_pem')],
    })

class TraefikService(BaseService):
    def __init__(self) -> None:
        super().__init__()
        self.run_profile = TraefikRunProfile()

if __name__ == "__main__":
    svc = TraefikService()
    svc.initialize()
    svc.start()
