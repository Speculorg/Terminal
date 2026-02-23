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
        return {
            StateEnum.INITIALIZING.value: ("consul_bootstrap", "consul_tokens"),
            StateEnum.SECURING.value: ("vault_init", "vault_initial_pem"),
            StateEnum.REGISTERING.value: ("consul_tokens", "vault_initial_pem"),
        }

    @property
    def start_cmd(self) -> Mapping[str, Sequence[str] | str | Any]:
        # TERM-1: hot-reload TLS без рестарта процесса.
        # Consul умеет перечитывать конфигурацию по SIGHUP (эквивалентно "consul reload"). :contentReference[oaicite:6]{index=6}
        #
        # Реализуем watcher прямо в start_cmd, чтобы ядро не знало про Consul и не рестартило процесс.
        return {
            "http": ("consul", "agent", "-config-file=/config/consul_http.hcl"),
            "https": (
                "sh",
                "-ec",
                "\n".join(
                    (
                        "CA=/fs/terminal/certs/ca.crt",
                        "CERT=/fs/terminal/certs/consul.crt",
                        "KEY=/fs/terminal/certs/consul.key",
                        "consul agent -config-file=/config/consul_https.hcl &",
                        "pid=$!",
                        "trap 'kill -TERM \"$pid\" 2>/dev/null || true; wait \"$pid\" 2>/dev/null || true' TERM INT",
                        "last=$( (sha256sum \"$CA\" \"$CERT\" \"$KEY\" 2>/dev/null || true) | sha256sum | awk '{print $1}')",
                        "while kill -0 \"$pid\" 2>/dev/null; do",
                        "  cur=$( (sha256sum \"$CA\" \"$CERT\" \"$KEY\" 2>/dev/null || true) | sha256sum | awk '{print $1}')",
                        "  if [ -n \"$cur\" ] && [ \"$cur\" != \"$last\" ]; then",
                        "    last=\"$cur\"",
                        "    echo 'consul_tls_watch: changed -> HUP'",
                        "    kill -HUP \"$pid\" 2>/dev/null || true",
                        "  fi",
                        "  sleep 1",
                        "done",
                        "wait \"$pid\"",
                    )
                ),
            ),
        }

    bootstrap_done_markers = ("consul_bootstrap", "consul_tokens")
    bootstrap_fn = staticmethod(consul_bootstrap)


class ConsulService(BaseService):
    def __init__(self) -> None:
        super().__init__(run_profile=ConsulRunProfile())


if __name__ == "__main__":
    ConsulService().run()