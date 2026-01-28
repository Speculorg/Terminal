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
        # Traefik:
        # - static config (/config/traefik.yml), no generation
        # - в SECURING переключается на HTTPS-only, inbound mTLS обязателен
        return {
            # ждём, пока Consul/Vault подготовят базовые артефакты
            StateEnum.BOOTSTRAPPING.value: ("vault_init", "vault_initial_pem", "consul_tokens"),
            # SECURING дополнительно ждёт, что traefik_bootstrap уже сгенерировал статический конфиг
            StateEnum.SECURING.value: ("vault_initial_pem", "consul_tokens", "traefik_bootstrap"),
        }

    @property
    def start_cmd(self) -> Mapping[str, Sequence[str] | str | Any]:
        return {
            "http": ("traefik", "--configFile=/config/traefik.yml"),
            "https": ("traefik", "--configFile=/config/traefik.yml"),
        }


class TraefikService(BaseService):
    def __init__(self) -> None:
        super().__init__(run_profile=TraefikRunProfile())


if __name__ == "__main__":
    TraefikService().run()
