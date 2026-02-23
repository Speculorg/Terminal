# services/vault/app/main.py
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
            StateEnum.SECURING.value: ("vault_init", "vault_initial_pem", "consul_ready"),
            StateEnum.REGISTERING.value: ("consul_tokens", "consul_ready"),
        }

    @property
    def start_cmd(self) -> Mapping[str, Sequence[str] | str | Any]:
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
                # Vault: после старта HTTPS может быть sealed; делаем autounseal, затем включаем hot-reload TLS через SIGHUP.
                # SIGHUP используется для reload listener TLS cert/key/ca, без рестарта/unseal. :contentReference[oaicite:7]{index=7}
                "\n".join(
                    (
                        'export CONSUL_HTTP_TOKEN="$(cat /fs/terminal/secrets/consul_token_for_vault)"',
                        "CA=/fs/terminal/certs/ca.crt",
                        "CERT=/fs/terminal/certs/vault.crt",
                        "KEY=/fs/terminal/certs/vault.key",
                        "ADDR=https://127.0.0.1:${VAULT_HTTP_PORT:-8200}",
                        "UNSEAL_KEYS=/fs/terminal/secrets/vault_unseal_keys.json",
                        "vault server -config=/config/vault_https.hcl &",
                        "pid=$!",
                        "trap 'kill -TERM \"$pid\" 2>/dev/null || true; wait \"$pid\" 2>/dev/null || true' TERM INT",
                        "# wait for HTTPS listener (seal-status is available even when sealed)",
                        "i=0",
                        "while [ $i -lt 240 ]; do",
                        "  if curl -sS --connect-timeout 1 --max-time 2 --cacert \"$CA\" --cert \"$CERT\" --key \"$KEY\" "
                        "\"$ADDR/v1/sys/seal-status\" >/tmp/vault_seal.json 2>/dev/null; then",
                        "    break",
                        "  fi",
                        "  i=$((i+1))",
                        "  sleep 0.25",
                        "done",
                        "if [ ! -s /tmp/vault_seal.json ]; then",
                        "  echo 'vault_https_unseal: seal-status timeout' >&2",
                        "  exit 1",
                        "fi",
                        "sealed=$(python3 -c 'import json; print(\"1\" if json.load(open(\"/tmp/vault_seal.json\"))[\"sealed\"] else \"0\")')",
                        "if [ \"$sealed\" = \"1\" ]; then",
                        "  echo 'vault_https_unseal: sealed=true -> unseal'",
                        "  if [ ! -s \"$UNSEAL_KEYS\" ]; then",
                        "    echo 'vault_https_unseal: missing unseal keys file' >&2",
                        "    exit 1",
                        "  fi",
                        "  python3 - <<'PY' | curl -sS --connect-timeout 1 --max-time 5 --cacert \"$CA\" --cert \"$CERT\" "
                        "--key \"$KEY\" -H 'Content-Type: application/json' -X POST --data-binary @- "
                        "\"$ADDR/v1/sys/unseal\" >/tmp/vault_unseal.json",
                        "import json",
                        "with open('/fs/terminal/secrets/vault_unseal_keys.json', 'r', encoding='utf-8') as f:",
                        "    key = (json.load(f).get('keys') or [''])[0]",
                        "print(json.dumps({'key': key}))",
                        "PY",
                        "  curl -sS --connect-timeout 1 --max-time 2 --cacert \"$CA\" --cert \"$CERT\" --key \"$KEY\" "
                        "\"$ADDR/v1/sys/seal-status\" >/tmp/vault_seal2.json 2>/dev/null || true",
                        "  sealed2=$(python3 -c 'import json; print(\"1\" if json.load(open(\"/tmp/vault_seal2.json\"))[\"sealed\"] else \"0\")' "
                        "2>/dev/null || echo 1)",
                        "  if [ \"$sealed2\" = \"1\" ]; then",
                        "    echo 'vault_https_unseal: unseal failed (still sealed)' >&2",
                        "    exit 1",
                        "  fi",
                        "  echo 'vault_https_unseal: unsealed'",
                        "fi",
                        "# hot-reload TLS: watch cert files and send HUP to vault process",
                        "last=$( (sha256sum \"$CA\" \"$CERT\" \"$KEY\" 2>/dev/null || true) | sha256sum | awk '{print $1}')",
                        "while kill -0 \"$pid\" 2>/dev/null; do",
                        "  cur=$( (sha256sum \"$CA\" \"$CERT\" \"$KEY\" 2>/dev/null || true) | sha256sum | awk '{print $1}')",
                        "  if [ -n \"$cur\" ] && [ \"$cur\" != \"$last\" ]; then",
                        "    last=\"$cur\"",
                        "    echo 'vault_tls_watch: changed -> HUP'",
                        "    kill -HUP \"$pid\" 2>/dev/null || true",
                        "  fi",
                        "  sleep 1",
                        "done",
                        "wait \"$pid\"",
                    )
                ),
            ),
        }

    bootstrap_done_markers = ("vault_init", "vault_initial_pem")
    bootstrap_fn = staticmethod(vault_bootstrap)


class VaultService(BaseService):
    def __init__(self) -> None:
        super().__init__(run_profile=VaultRunProfile())


if __name__ == "__main__":
    VaultService().run()