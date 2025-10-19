from __future__ import annotations
from dataclasses import dataclass
from entities.state_enum import StateEnum

@dataclass
class RegistrarPolicy:
    cfg: object

    def on_register(self) -> bool:
        # В TERM-1 регистратор будет подключён на этапе 10. Пока разрешаем переход.
        return True

    def on_deregister(self) -> bool:
        return True
