# source\services\consul\config\init-consul.py


from __future__ import annotations
import json
import logging
import sys
import time
import requests
from pathlib import Path
from typing import Dict
sys.path.append("/")
from core.base.settings import settings # pylint: disable=wrong-import-position


# --------------------------------------------------------------------------- #
#                                   Constants                                 #
# --------------------------------------------------------------------------- #
CONSUL_ADDR = f"http://{settings.CONSUL_HOST}:{settings.CONSUL_PORT}"

SECRETS_DIR      = Path("/consul/secrets")
ROOT_TOKEN_JSON  = SECRETS_DIR / "root_consul_token.json"

AGENT_TOKEN_FILE = SECRETS_DIR / "agent_consul_token"
VAULT_TOKEN      = SECRETS_DIR / "vault_consul_token"
TRAEFIK_TOKEN    = SECRETS_DIR / "traefik_consul_token"

POLICIES: Dict[str, Dict] = {
    "agent": {
        "name": "agent-policy",
        "rules": """
            agent          "" { policy = "write" }
            node_prefix    "" { policy = "write" }
            service_prefix "" { policy = "read"  }
            """,
        "token_file": AGENT_TOKEN_FILE,
        "desc": "token-for-consul-agent",
    },
    "vault": {
        "name": "vault-policy",
        "rules": """
            key_prefix "vault/" { policy = "write" }
            service    "vault"  { policy = "write" }
            service_prefix ""   { policy = "write" }
            session_prefix ""   { policy = "write" }
            node_prefix    ""   { policy = "write" }
            agent          ""   { policy = "write" }
            """,
        "token_file": VAULT_TOKEN,
        "desc": "token-for-vault",
    },
    "traefik": {
        "name": "traefik-policy",
        "rules": """
            node_prefix    "" { policy = "read"  }
            query_prefix   "" { policy = "read"  }
            agent          "" { policy = "write" }
            service_prefix "" { policy = "write" }
            """,
        "token_file": TRAEFIK_TOKEN,
        "desc": "token-for-traefik",
    },
}


# --------------------------------------------------------------------------- #
#                                   Logging                                   #
# --------------------------------------------------------------------------- #
logger = logging.getLogger("consul")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
if not logger.handlers:
    logger.addHandler(handler)


def _fatal(msg: str) -> None:
    logger.error(msg)
    sys.exit(1)


# --------------------------------------------------------------------------- #
#                               Helpers                                       #
# --------------------------------------------------------------------------- #
def wait_for_ready(timeout: int = 30) -> None:
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


def _api(method: str, path: str, **kw):
    return requests.request(method, f"{CONSUL_ADDR}{path}", timeout=5, **kw)


# --------------------------------------------------------------------------- #
#                                   Main                                      #
# --------------------------------------------------------------------------- #
def main() -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    if AGENT_TOKEN_FILE.exists():
        logger.info("Already exists: agent-token -> nothing to do")
        return

    wait_for_ready()

    # ---------------- ACL bootstrap ----------------
    r = _api("PUT", "/v1/acl/bootstrap")
    if r.status_code != 200:
        _fatal(f"ACL bootstrap failed: {r.status_code} {r.text}")

    root_token = r.json()["SecretID"]
    ROOT_TOKEN_JSON.write_text(r.text)
    logger.info("Root token saved -> %s", ROOT_TOKEN_JSON)

    hdr = {"X-Consul-Token": root_token}

    # ---------------- policies + tokens ----------------
    current = {p["Name"] for p in _api("GET", "/v1/acl/policies", headers=hdr).json()}

    for name, cfg in POLICIES.items():
        if cfg["name"] not in current:
            _api("PUT", "/v1/acl/policy", headers=hdr, json={
                "Name": cfg["name"],
                "Description": f"auto {name}",
                "Rules": cfg["rules"],
            })
            logger.info("Policy created: %s", cfg["name"])
        else:
            logger.info("Policy exists: %s", cfg["name"])

        token = _api("PUT", "/v1/acl/token", headers=hdr, json={
            "Description": cfg["desc"],
            "Policies": [{"Name": cfg["name"]}],
        }).json()["SecretID"]

        cfg["token_file"].write_text(token)
        logger.info("Token saved -> %s", cfg["token_file"])

    logger.info("OK - init-consul done")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc: # pylint: disable=broad-except
        _fatal(str(exc))
