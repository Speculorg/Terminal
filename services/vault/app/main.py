from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from core._base import BaseService
from core._entities import StateEnum
from core._interfaces import IRunProfile

from services.vault.config.bootstrap import vault_bootstrap


@dataclass(frozen=True)
class VaultRunProfile(IRunProfile):
    """RunProfile для Vault (TERM-1)."""

    @property
    def stage_gates(self) -> Mapping[str, Sequence[str]]:
        return {
            StateEnum.INITIALIZING.value: ("vault_init", "vault_initial_pem"),
            StateEnum.BOOTSTRAPPING.value: ("consul_tokens",),
            StateEnum.SECURING.value: ("vault_init", "vault_initial_pem"),
            # регистрация только после готовности токенов Consul и готовности самого Consul
            StateEnum.REGISTERING.value: ("consul_tokens", "consul_ready"),
        }

    @property
    def start_cmd(self) -> Mapping[str, Sequence[str] | str | Any]:
        # Vault Consul storage требует ACL token (CONSUL_HTTP_TOKEN).
        # Токен создаёт Consul bootstrap и пишет в FS; здесь подхватываем его без добавления новых сущностей.
        return {
            "http": (
                "sh",
                "-ec",
                'export CONSUL_HTTP_TOKEN="$(cat /fs/terminal/secrets/consul_token_for_vault)"; '
                "exec vault server -config=/config/vault_http.hcl",
            ),
            "https": (
                "sh",
                "-ec",
                'export CONSUL_HTTP_TOKEN="$(cat /fs/terminal/secrets/consul_token_for_vault)"; '
                "exec vault server -config=/config/vault_https.hcl",
            ),
        }

    bootstrap_done_markers = ("vault_init", "vault_initial_pem")
    bootstrap_fn = staticmethod(vault_bootstrap)


class VaultService(BaseService):
    def __init__(self) -> None:
        super().__init__(run_profile=VaultRunProfile())


if __name__ == "__main__":
    VaultService().run()
