from __future__ import annotations
from dataclasses import dataclass
from entities.state_enum import StateEnum

@dataclass
class KVPolicy:
    cfg: object

    def can_publish_states(self, state: StateEnum) -> bool:
        # Публикация в KV разрешена только в RUNNING согласно плану.
        return state.name == "RUNNING"
