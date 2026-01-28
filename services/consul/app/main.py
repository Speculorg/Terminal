from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from core._base import BaseService
from core._entities import StateEnum
from core._interfaces import IRunProfile

from services.consul.config.bootstrap import consul_bootstrap


@dataclass(frozen=True)
class ConsulRunProfile(IRunProfile):
    """RunProfile для Consul (TERM-1)."""

    @property
    def stage_gates(self) -> Mapping[str, Sequence[str]]:
        # В TERM-1 Consul зависит от Vault PKI (CA + initial PEM), чтобы перейти в SECURING/HTTPS.
        # REGISTERING можно использовать позже для согласования с другими шагами (например, токены/ACL).
        return {
            StateEnum.SECURING.value: ("vault_init", "vault_initial_pem"),
            StateEnum.REGISTERING.value: ("consul_tokens", "vault_initial_pem"),
        }

    @property
    def start_cmd(self) -> Mapping[str, Sequence[str] | str | Any]:
        return {
            "http": ("consul", "agent", "-config-file=/config/consul_http.hcl"),
            "https": ("consul", "agent", "-config-file=/config/consul_https.hcl"),
        }

    # Duck-typing hooks, используемые BaseService.build_fsm()
    bootstrap_done_markers = ("consul_bootstrap", "consul_tokens")
    bootstrap_fn = staticmethod(consul_bootstrap)


class ConsulService(BaseService):
    def __init__(self) -> None:
        super().__init__(run_profile=ConsulRunProfile())


if __name__ == "__main__":
    ConsulService().run()
