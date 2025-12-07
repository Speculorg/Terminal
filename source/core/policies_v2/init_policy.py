from __future__ import annotations
from base.base_policy import BasePolicy
from interfaces.i_policy import PolicyResult, PolicyStatus
from entities import StateEnum

class InitPolicy(BasePolicy):
    def __init__(self, logger, cfg, fs, markers, net, state: StateEnum):
        super().__init__(logger)
        self.cfg, self.fs, self.markers, self.net, self.state = cfg, fs, markers, net, state

    def _run(self) -> PolicyResult:
        try:
            from core.policies.init_policy import InitPolicy as LegacyInit
            pol = LegacyInit(self.cfg, self.logger, self.fs, self.markers, self.net)
            nxt = pol.apply(self.state)
            return PolicyResult(PolicyStatus.OK, {"next": getattr(nxt, "name", None)})
        except Exception as e:
            self.logger.warn("policy.init.legacy.absent", details={"error": str(e)})
            return PolicyResult(PolicyStatus.OK)
