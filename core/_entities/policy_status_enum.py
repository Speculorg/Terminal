"""
speculorg.terminal.core._entities.policy_status_enum
====================================================

Перечисление статусов результата политики.
"""

from enum import Enum

class PolicyStatusEnum(str, Enum):
    OK = "OK"
    RETRY = "RETRY"
    FAIL = "FAIL"
