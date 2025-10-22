
from __future__ import annotations
from dataclasses import dataclass, field
from base import BaseService
from interfaces import IRunProfile
from entities.state_enum import StateEnum

@dataclass(frozen=True)
class ConsulRunProfile(IRunProfile):
    required_markers: set[str] = field(default_factory=lambda: {'bootstrap.done','tokens.done'})
    stage_gates: dict = field(default_factory=lambda: {
        StateEnum.SECURING: [('vault','init'), ('certs','initial_pem')],
        StateEnum.REGISTERING: [('consul','tokens'), ('certs','initial_pem')],
    })

class ConsulService(BaseService):
    def __init__(self) -> None:
        super().__init__()
        self.run_profile = ConsulRunProfile()

if __name__ == "__main__":
    svc = ConsulService()
    svc.initialize()
    svc.start()
