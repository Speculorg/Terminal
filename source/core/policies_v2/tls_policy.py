from __future__ import annotations
from base.base_policy import BasePolicy
from interfaces.i_policy import PolicyResult, PolicyStatus
from core.policies import TLSPolicy as LegacyTLS

class TLSPolicy(BasePolicy):
    def __init__(self, logger, cfg, markers, net, profile, mode_resolver, restart_cb):
        super().__init__(logger)
        self.cfg, self.markers, self.net, self.profile = cfg, markers, net, profile
        self.mode_resolver, self.restart_cb = mode_resolver, restart_cb

    def _run(self) -> PolicyResult:
        try:
            LegacyTLS().transition_if_ready(
                self.cfg, self.logger, self.markers, self.net, self.profile,
                current_mode="http", restart_cb=self.restart_cb, resolve_port_cb=self.mode_resolver
            )
            return PolicyResult(PolicyStatus.OK)
        except Exception as e:
            self.logger.warn("policy.tls.transition.retry", details={"error": str(e)})
            return PolicyResult(PolicyStatus.RETRY, {"error": str(e)})
