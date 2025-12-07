from __future__ import annotations
from base.base_policy import BasePolicy
from interfaces.i_policy import PolicyResult, PolicyStatus
from core.policies.daemon_policy import DaemonPolicy as LegacyDaemon

class PortReadyPolicy(BasePolicy):
    def __init__(self, logger, cfg, net, profile, mode: str = "http"):
        super().__init__(logger)
        self.cfg, self.net, self.profile, self.mode = cfg, net, profile, mode

    def _run(self) -> PolicyResult:
        try:
            port = LegacyDaemon.resolve_port(self.cfg, self.profile, self.mode)
            host = "127.0.0.1"
            self.net.wait_port(host, port)
            return PolicyResult(PolicyStatus.OK, {"port": port})
        except Exception as e:
            self.logger.warn("policy.port.wait.retry", details={"error": str(e)})
            return PolicyResult(PolicyStatus.RETRY, {"error": str(e)})
