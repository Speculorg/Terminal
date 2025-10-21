from __future__ import annotations
from dataclasses import dataclass
from base import BaseService
from interfaces import IRunProfile

@dataclass(frozen=True)
class TraefikRunProfile(IRunProfile):
    required_markers: set[str]

class TraefikService(BaseService):
    def __init__(self) -> None:
        super().__init__()
        # Требуемые маркеры задаём именами файлов, без префикса пути и svc
        self.run_profile = TraefikRunProfile(required_markers={'initial_pem.done'})

if __name__ == "__main__":
    svc = TraefikService()
    svc.initialize()
    svc.start()
