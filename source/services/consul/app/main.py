from __future__ import annotations
from dataclasses import dataclass
from base.base_service import BaseService
from interfaces.i_run_profile import IRunProfile

@dataclass
class ConsulRunProfile(IRunProfile):
    required_markers: set[str]

class ConsulService(BaseService):
    def __init__(self) -> None:
        super().__init__()
        self.run_profile = ConsulRunProfile(required_markers={'fs/markers/consul/bootstrap.done', 'fs/markers/consul/tokens.done'})

if __name__ == "__main__":
    svc = ConsulService()
    svc.initialize()
    svc.start()
