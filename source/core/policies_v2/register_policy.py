from __future__ import annotations
from base.base_policy import BasePolicy
from interfaces.i_policy import PolicyResult, PolicyStatus

class RegisterPolicy(BasePolicy):
    def _run(self) -> PolicyResult:
        return PolicyResult(PolicyStatus.OK)
