"""
speculorg.terminal.core._entities.log_level_enum
================================================

Перечисление уровней логирования.
"""
from enum import Enum


class LogLevelEnum(Enum):
    """
    Уровни логирования, соответствуют стандартным уровням logging в Python.
    """
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
