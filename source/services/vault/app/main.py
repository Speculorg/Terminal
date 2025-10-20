from __future__ import annotations
from dataclasses import dataclass
from base.base_service import BaseService
from interfaces.i_run_profile import IRunProfile

@dataclass
class VaultRunProfile(IRunProfile):
    required_markers: set[str]

class VaultService(BaseService):
    def __init__(self) -> None:
        super().__init__()
        self.run_profile = VaultRunProfile(required_markers={'fs/markers/vault/pki.done', 'fs/markers/vault/unseal.done', 'fs/markers/vault/init.done'})

if __name__ == "__main__":
    svc = VaultService()
    svc.initialize()
    svc.start()
