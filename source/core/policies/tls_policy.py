from __future__ import annotations
from dataclasses import dataclass
from entities.state_enum import StateEnum

@dataclass
class TLSPolicy:
    cfg: object

    def check_ready(self) -> bool:
        # На ранних стадиях опираемся на маркеры/файлы, сетевых проб не делаем в TERM-1.
        return True

    def https_probes_ok(self) -> bool:
        # Допустим проверку успешной готовности HTTPS при переключении, но пока возвращаем True.
        return True
