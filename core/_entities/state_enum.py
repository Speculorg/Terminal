"""
speculorg.terminal.core._entities.state_enum
============================================

Перечисление состояний FSM сервиса.
"""

from enum import Enum

class StateEnum(str, Enum):
    STARTING = "STARTING"
    INITIALIZING = "INITIALIZING"
    BOOTSTRAPPING = "BOOTSTRAPPING"
    SECURING = "SECURING"
    REGISTERING = "REGISTERING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
