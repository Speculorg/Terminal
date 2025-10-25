from __future__ import annotations
from dataclasses import dataclass

from base import BaseService
from interfaces import IRunProfile
from entities.state_enum import StateEnum

@dataclass(frozen=True)
class TraefikRunProfile(IRunProfile):
    required_markers = None
    stage_gates = {
        StateEnum.SECURING: { "consul_tokens.done", "vault_initial_pem.done" },
        StateEnum.REGISTERING: { "consul_tokens.done", "vault_initial_pem.done" },
    }


class TraefikService(BaseService):
    def __init__(self) -> None:
        super().__init__(TraefikRunProfile())


if __name__ == "__main__":
    svc = TraefikService()
