from __future__ import annotations
from dataclasses import dataclass
from base import BaseService
from interfaces import IRunProfile

@dataclass(frozen=True)
class VaultRunProfile(IRunProfile):
    required_markers: set[str]

class VaultService(BaseService):
    def __init__(self) -> None:
        super().__init__()
        # Требуемые маркеры задаём именами файлов, без префикса пути и svc
        self.run_profile = VaultRunProfile(required_markers={'init.done','unseal.done','pki.done'})

if __name__ == "__main__":
    svc = VaultService()
    svc.initialize()
    svc.start()
