"""
speculorg.terminal.core._entities.policy_result_type
====================================================

Тип данных для результата выполнения политики (PolicyResult).
"""
from typing import Optional, Any, Dict
from .policy_status_enum import PolicyStatusEnum


class PolicyResultType(Dict[str, Any]):
    """
    Структура данных результата выполнения политики.
    """
    status: PolicyStatusEnum
    details: Optional[Dict[str, Any]]