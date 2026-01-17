# Пакет сущностей ядра
"""
speculorg.terminal.core._entities
=================================

Доменные сущности, перечисления, типы данных.
"""

from .health_snapshot_type import HealthSnapshotType
from .policy_result_type import PolicyResultType

from .error_code_enum import ErrorCodeEnum
from .event_code_enum import EventCodeEnum
from .log_level_enum import LogLevelEnum
from .policy_status_enum import PolicyStatusEnum
from .run_mode_enum import RunModeEnum
from .state_enum import StateEnum

__all__ = [
    "HealthSnapshotType",
    "PolicyResultType",
    "ErrorCodeEnum",
    "EventCodeEnum",
    "LogLevelEnum",
    "PolicyStatusEnum",
    "RunModeEnum",
    "StateEnum",
]
