from __future__ import annotations
from typing import Optional
from interfaces.i_policy import IPolicy, PolicyResult, PolicyStatus

class BasePolicy(IPolicy):
    def __init__(self, logger, context: Optional[dict] = None) -> None:
        self.logger = logger
        self.context = context or {}

    def run(self) -> PolicyResult:
        try:
            self.logger.info("policy.run.start", details={"policy": self.__class__.__name__})
            res = self._run()
            if not isinstance(res, PolicyResult):
                return PolicyResult(PolicyStatus.FAIL, {"reason": "invalid_result"})
            self.logger.info("policy.run.done", details={"policy": self.__class__.__name__, "status": res.status})
            return res
        except Exception as e:
            self.logger.error("policy.run.exception", details={"policy": self.__class__.__name__, "error": str(e)})
            return PolicyResult(PolicyStatus.FAIL, {"exception": str(e)})

    def _run(self) -> PolicyResult:
        return PolicyResult(PolicyStatus.OK)
