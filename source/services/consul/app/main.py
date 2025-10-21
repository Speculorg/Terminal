from __future__ import annotations
from dataclasses import dataclass
from base import BaseService
from interfaces import IRunProfile

@dataclass(frozen=True)
class ConsulRunProfile(IRunProfile):
    required_markers: set[str]

class ConsulService(BaseService):
    def __init__(self) -> None:
        super().__init__()
        # Требуемые маркеры задаём именами файлов, без префикса пути и svc
        self.run_profile = ConsulRunProfile(required_markers={'bootstrap.done','tokens.done'})

if __name__ == "__main__":
    svc = ConsulService()
    svc.initialize()
    svc.start()
