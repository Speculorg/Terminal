"""
speculorg.terminal.core._entities.policy_result_type
====================================================

Тип данных для результата выполнения политики (PolicyResult).
"""

from __future__ import annotations
from typing import Optional, TypedDict
from .policy_status_enum import PolicyStatusEnum

class PolicyResultType(TypedDict, total=False):
    """
    Result returned by policy execution.

    Contract:
      - status: required signal for FSM
      - details: optional JSON-serializable dict

    Details keys (common contract):
      - error_code: str (value from ErrorCodeEnum) REQUIRED for FAIL
      - reason: str (one-line technical reason)
      - missing: list[str] (missing gates/markers/etc.)
      - meta: dict[str, object] (policy-specific extra info)
    """

    status: PolicyStatusEnum
    details: Optional[dict[str, object]]
