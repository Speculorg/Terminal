from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from core._base import BaseService
from core._entities import StateEnum
from core._interfaces import IRunProfile


@dataclass(frozen=True)
class TraefikRunProfile(IRunProfile):
    """RunProfile для Traefik (TERM-1)."""

    @property
    def stage_gates(self) -> Mapping[str, Sequence[str]]:
        # Traefik bootstrap не требуется.
        # Старт демона блокируем по маркерам: ждём токены Consul и первичные артефакты PKI от Vault.
        return {
            StateEnum.BOOTSTRAPPING.value: ("vault_initial_pem", "consul_tokens"),
            StateEnum.SECURING.value: ("vault_initial_pem", "consul_tokens"),
            # регистрация только после готовности токенов Consul и готовности самого Consul
            StateEnum.REGISTERING.value: ("consul_tokens", "consul_ready"),
        }

    @property
    def start_cmd(self) -> Mapping[str, Sequence[str] | str | Any]:
        # Traefik работает только в HTTPS (mTLS). HTTP режим не используется.
        return {
            "https": ("traefik", "--configFile=/config/traefik.yml"),
        }


class TraefikService(BaseService):
    def __init__(self) -> None:
        super().__init__(run_profile=TraefikRunProfile())


if __name__ == "__main__":
    TraefikService().run()
