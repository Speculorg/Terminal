# source\services\consul\config\init-consul.py

"""
One-shot Consul ACL bootstrap & token issuance.

- If   /consul/secrets/agent_consul_token   already exists → just exit 0
- Else bootstrap ACL, create policies, issue tokens, save them under
   /consul/secrets/*.  No retries on errors - container will crash and log.

"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict

import requests


# ───────────── PATHS & CONST ────────────────────────────────────────────
CONSUL_ADDR = "http://localhost:8500"
SECRETS_DIR = Path("/consul/secrets")
SECRETS_DIR.mkdir(parents=True, exist_ok=True)

ROOT_TOKEN_FILE = SECRETS_DIR / "root_consul_token.json"
AGENT_TOKEN_FILE = SECRETS_DIR / "agent_consul_token"
REGISTER_TOKEN_FILE = SECRETS_DIR / "registering_consul_token"
VAULT_TOKEN_FILE = SECRETS_DIR / "vault_consul_token"
TRAEFIK_TOKEN_FILE = SECRETS_DIR / "traefik_consul_token"

POLICIES: Dict[str, Dict] = {
    "agent": {
        "name": "agent-policy",
        "rules": """
            # управление собственным агентом
            agent       ""  { policy = "write" }

            # запись координационных данных / health-чеков узла
            node_prefix ""  { policy = "write" }

            # чтение всех сервисов (чтобы видеть, кто зареган)
            service_prefix "" { policy = "read" }
        """,
        "token_file": AGENT_TOKEN_FILE,
        "desc": "token-for-consul-agent",
    },

    "register": {
        "name": "registering-policy",
        "rules": """
            agent          "" { policy = "write" }
            service_prefix "" { policy = "write" }
        """,
        "token_file": REGISTER_TOKEN_FILE,
        "desc": "token-for-service-registration",
    },

    "vault": {
        "name": "vault-policy",
        "rules": """
            key_prefix "vault/" { policy = "write" }
            service_prefix ""   { policy = "read"  }
            node_prefix    ""   { policy = "read"  }
        """,
        "token_file": VAULT_TOKEN_FILE,
        "desc": "token-for-vault",
    },

    "traefik": {
        "name": "traefik-policy",
        "rules": """
            service_prefix "" { policy = "read" }
            node_prefix    "" { policy = "read" }
            query_prefix   "" { policy = "read" }
        """,
        "token_file": TRAEFIK_TOKEN_FILE,
        "desc": "token-for-traefik",
    },
}


# ───────────── LOGGING ──────────────────────────────────────────────────
log = logging.getLogger("init-consul")
log.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
log.addHandler(handler)


def _fatal(msg: str) -> None:
    log.error(msg)
    sys.exit(1)


# ───────────── HTTP HELPERS ─────────────────────────────────────────────
def _wait_for_leader(timeout: int = 30) -> None:
    url = f"{CONSUL_ADDR}/v1/status/leader"
    end = time.time() + timeout
    while time.time() < end:
        try:
            r = requests.get(url, timeout=2)
            if r.ok and r.text and r.text != '""':
                return
        except Exception:
            pass
        time.sleep(1)
    _fatal("Consul leader not ready")


def _http(method: str, path: str, **kw):
    return requests.request(method, f"{CONSUL_ADDR}{path}", timeout=5, **kw)


# ───────────── ACL bootstrap ────────────────────────────────────────────
def main() -> None:

    # already initialised?
    if AGENT_TOKEN_FILE.exists():
        log.info("Agent token found - nothing to do.")
        return

    _wait_for_leader()

    # bootstrap → root token
    r = _http("PUT", "/v1/acl/bootstrap")
    if r.status_code != 200:
        _fatal(f"ACL bootstrap failed: {r.status_code} {r.text}")

    root_token = r.json()["SecretID"]
    ROOT_TOKEN_FILE.write_text(r.text)
    log.info("ACL bootstrap complete - root token saved")

    headers = {"X-Consul-Token": root_token}

    # create / update policies & tokens
    existing = [p["Name"] for p in _http("GET", "/v1/acl/policies", headers=headers).json()]

    for role, cfg in POLICIES.items():
        if cfg["name"] not in existing:
            payload = {
                "Name": cfg["name"],
                "Description": f"auto {role}",
                "Rules": cfg["rules"],
            }
            _http("PUT", "/v1/acl/policy", headers=headers, json=payload)
            log.info("Policy %s created", cfg["name"])
        else:
            log.info("Policy %s already exists", cfg["name"])

        token = _http(
            "PUT",
            "/v1/acl/token",
            headers=headers,
            json={"Description": cfg["desc"], "Policies": [{"Name": cfg["name"]}]},
        ).json()["SecretID"]
        cfg["token_file"].write_text(token)
        log.info("Token for %s saved → %s", role, cfg["token_file"])

    log.info("All done - exit 0")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        _fatal(str(exc))
