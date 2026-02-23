# services/traefik/app/main.py
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
            StateEnum.SECURING.value: ("vault_initial_pem", "consul_tokens", "consul_ready"),
            StateEnum.REGISTERING.value: ("consul_tokens", "consul_ready"),
        }

    @property
    def start_cmd(self) -> Mapping[str, Sequence[str] | str | Any]:
        # TERM-1: Traefik работает только в HTTPS (mTLS).
        #
        # Важно: file provider watch отслеживает изменения динамической конфигурации.
        # Замена cert/key файлов может НЕ триггерить reload, если динамический файл не меняется.
        # Поэтому делаем service-local watcher: при изменении cert/key -> touch /config/traefik_dynamic.yml.
        #
        # Это НЕ рестарт и НЕ сигнал, процесс остаётся тем же.
        return {
            "https": (
                "sh",
                "-ec",
                "\n".join(
                    (
                        "DYN=/config/traefik_dynamic.yml",
                        "CA=/fs/terminal/certs/ca.crt",
                        "CERT=/fs/terminal/certs/traefik.crt",
                        "KEY=/fs/terminal/certs/traefik.key",
                        "traefik --configFile=/config/traefik.yml &",
                        "pid=$!",
                        "trap 'kill -TERM \"$pid\" 2>/dev/null || true; wait \"$pid\" 2>/dev/null || true' TERM INT",
                        # используем cksum: максимально вероятно доступен даже в минимальных образах
                        "last=$(cksum \"$CA\" \"$CERT\" \"$KEY\" 2>/dev/null || true)",
                        "while kill -0 \"$pid\" 2>/dev/null; do",
                        "  cur=$(cksum \"$CA\" \"$CERT\" \"$KEY\" 2>/dev/null || true)",
                        "  if [ -n \"$cur\" ] && [ \"$cur\" != \"$last\" ]; then",
                        "    last=\"$cur\"",
                        "    echo 'traefik_tls_watch: changed -> touch dynamic'",
                        "    touch \"$DYN\" 2>/dev/null || true",
                        "  fi",
                        "  sleep 1",
                        "done",
                        "wait \"$pid\"",
                    )
                ),
            ),
        }


class TraefikService(BaseService):
    def __init__(self) -> None:
        super().__init__(run_profile=TraefikRunProfile())


if __name__ == "__main__":
    TraefikService().run()