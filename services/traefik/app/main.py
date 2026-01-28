from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from core._base import BaseService
from core._entities import StateEnum
from core._interfaces import IRunProfile

from services.traefik.config.bootstrap import traefik_bootstrap


@dataclass(frozen=True)
class TraefikRunProfile(IRunProfile):
    """RunProfile для Traefik (TERM-1)."""

    @property
    def stage_gates(self) -> Mapping[str, Sequence[str]]:
        # Traefik в HTTPS требует PEM-контур (CA + leaf cert) от Vault PKI
        # и доступ к Consul (токены/ACL) для Consul Catalog.
                return {
            StateEnum.BOOTSTRAPPING.value: ("consul_tokens", "vault_init", "vault_initial_pem"),
            StateEnum.SECURING.value: ("vault_init", "vault_initial_pem", "consul_tokens", "traefik_bootstrap"),
        }

    @property
    def start_cmd(self) -> Mapping[str, Sequence[str] | str | Any]:
        return {
            "http": ("traefik", "--configFile=/config/traefik_http.yml"),
            "https": ("traefik", "--configFile=/config/traefik_https.generated.yml"),
        }



    @property
    def bootstrap_fn(self):
        return traefik_bootstrap

    bootstrap_done_markers = ("traefik_bootstrap",)


class TraefikService(BaseService):
    def __init__(self) -> None:
        super().__init__(run_profile=TraefikRunProfile())


if __name__ == "__main__":
    TraefikService().run()
