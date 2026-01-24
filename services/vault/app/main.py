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
        # Vault сам себе не зависит (bootstrap делает init/unseal/PKI и пишет PEM в FS).
        # REGISTERING оставляем пустым на TERM-1.
        return {
            StateEnum.SECURING.value: ("vault_init.done", "vault_initial_pem.done"),
        }

    @property
    def start_cmd(self) -> Mapping[str, Sequence[str] | str | Any]:
        return {
            "http": ("vault", "server", "-config=/config/vault_http.hcl"),
            "https": ("vault", "server", "-config=/config/vault_https.hcl"),
        }

    # Duck-typing hooks, используемые BaseService.build_fsm()
    bootstrap_done_markers = ("vault_init.done", "vault_initial_pem.done")
    bootstrap_fn = staticmethod(vault_bootstrap)


class VaultService(BaseService):
    def __init__(self) -> None:
        super().__init__(run_profile=VaultRunProfile())


if __name__ == "__main__":
    VaultService().run()
