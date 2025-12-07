from __future__ import annotations
from base.base_policy import BasePolicy
from interfaces.i_policy import PolicyResult, PolicyStatus
from core.policies.daemon_policy import DaemonPolicy as LegacyDaemon

class DaemonPolicy(BasePolicy):
    def __init__(self, logger, cfg, profile):
        super().__init__(logger)
        self.cfg, self.profile = cfg, profile

    def _run(self) -> PolicyResult:
        try:
            LegacyDaemon.decide_initial_mode(self.cfg)
        except Exception:
            pass
        return PolicyResult(PolicyStatus.OK)
