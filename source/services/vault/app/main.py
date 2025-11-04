from __future__ import annotations
from dataclasses import dataclass

from base import BaseService
from interfaces import IRunProfile
from entities import StateEnum


@dataclass(frozen=True)
class VaultRunProfile(IRunProfile):
    required_markers = {
        "vault_init.done",
        "vault_unseal.done",
        "vault_pki.done",
    }
    stage_gates = {
        StateEnum.STARTING: { "consul_tokens.done" },
        StateEnum.SECURING: { "vault_pki.done", "vault_initial_pem.done" },
        StateEnum.REGISTERING: { "vault_pki.done", "vault_initial_pem.done" },
    }
    start_cmd = {
        'http': ['vault', 'server', '-config=/config/vault_http.hcl'],
        'https': ['vault', 'server', '-config=/config/vault_https.hcl']
    }


class VaultService(BaseService):
    def __init__(self) -> None:
        super().__init__(VaultRunProfile())


if __name__ == "__main__":
    svc = VaultService()
    svc.run()
