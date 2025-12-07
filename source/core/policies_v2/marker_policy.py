from __future__ import annotations
from typing import List
from base.base_policy import BasePolicy
from interfaces.i_policy import PolicyResult, PolicyStatus
from entities import StateEnum

class MarkerPolicy(BasePolicy):
    def __init__(self, logger, markers, profile, state: StateEnum, *, strict: bool = True):
        super().__init__(logger)
        self.markers, self.profile, self.state, self.strict = markers, profile, state, strict

    def _run(self) -> PolicyResult:
        required = list(self.profile.stage_gates.get(self.state, []) or [])
        if not required:
            return PolicyResult(PolicyStatus.OK, {"required": []})
        missing: List[str] = [m for m in required if not self.markers.exists(m)]
        if missing:
            self.logger.warn("policy.marker.missing", state=self.state.name, details={"missing": sorted(missing)})
            return PolicyResult(PolicyStatus.OK if not self.strict else PolicyStatus.RETRY, {"missing": missing})
        return PolicyResult(PolicyStatus.OK, {"required": required})
