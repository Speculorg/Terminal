
from __future__ import annotations
from dataclasses import dataclass, field
from base import BaseService
from interfaces import IRunProfile
from entities.state_enum import StateEnum

@dataclass(frozen=True)
class ConsulRunProfile(IRunProfile):
    required_markers = { "consul_bootstrap.done", "consul_tokens.done" }
    stage_gates = {
        StateEnum.SECURING: { "vault_init.done", "vault_initial_pem.done" },
        StateEnum.REGISTERING: { "consul_tokens.done", "vault_initial_pem.done" },
    }

class ConsulService(BaseService):
    def __init__(self) -> None:
        super().__init__()
        self.run_profile = ConsulRunProfile()

if __name__ == "__main__":
    svc = ConsulService()
    svc.initialize()
    svc.start()
