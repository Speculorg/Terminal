from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

class PolicyStatus(str, Enum):
    OK = "ok"
    RETRY = "retry"
    FAIL = "fail"

@dataclass(frozen=True)
class PolicyResult:
    status: PolicyStatus
    details: Optional[Dict[str, Any]] = None

class IPolicy(ABC):
    @abstractmethod
    def run(self) -> PolicyResult: ...
