"""
speculorg.terminal.core._entities.log_level_enum
================================================

Перечисление уровней логирования.
"""

from enum import Enum

class LogLevelEnum(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
