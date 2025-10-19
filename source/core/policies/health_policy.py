from __future__ import annotations
from dataclasses import dataclass

@dataclass
class HealthPolicy:
    cfg: object
    # Эскалация/окна деградации реализуются в TERM-1 минимально. Расширим в последующих этапах.
