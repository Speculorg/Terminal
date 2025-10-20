from __future__ import annotations
from dataclasses import dataclass
from base.base_service import BaseService
from interfaces.i_run_profile import IRunProfile

@dataclass
class TraefikRunProfile(IRunProfile):
    required_markers: set[str]

class TraefikService(BaseService):
    def __init__(self) -> None:
        super().__init__()
        self.run_profile = TraefikRunProfile(required_markers={'fs/markers/certs/initial_pem.done'})

if __name__ == "__main__":
    svc = TraefikService()
    svc.initialize()
    svc.start()
