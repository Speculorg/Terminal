"""
speculorg.terminal.core._entities.run_mode_enum
===============================================

Перечисление режимов запуска сервиса.
"""

from enum import Enum

class RunModeEnum(str, Enum):
    FIRST = "FIRST"
    NORMAL = "NORMAL"
