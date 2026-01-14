"""
speculorg.terminal.core._entities.run_mode_enum
===============================================

Перечисление режимов запуска сервиса.
"""
from enum import Enum


class RunModeEnum(Enum):
    """
    Режим запуска сервиса.
    """
    FIRST = "FIRST"   # Первый запуск, требует инициализации
    NORMAL = "NORMAL" # Повторный запуск
