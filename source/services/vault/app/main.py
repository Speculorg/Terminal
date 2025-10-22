
from __future__ import annotations
from dataclasses import dataclass, field
from base import BaseService
from interfaces import IRunProfile
from entities.state_enum import StateEnum

@dataclass(frozen=True)
class VaultRunProfile(IRunProfile):
    required_markers: set[str] = field(default_factory=lambda: {'init.done','unseal.done','pki.done'})
    stage_gates: dict = field(default_factory=lambda: {
        StateEnum.STARTING: [('consul','tokens')],
        StateEnum.SECURING: [('vault','pki'), ('certs','initial_pem')],
        StateEnum.REGISTERING: [('vault','pki'), ('certs','initial_pem')],
    })

class VaultService(BaseService):
    def __init__(self) -> None:
        super().__init__()
        self.run_profile = VaultRunProfile()

if __name__ == "__main__":
    svc = VaultService()
    svc.initialize()
    svc.start()
