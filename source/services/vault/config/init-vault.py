# source\services\vault\config\init-vault.py


from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict

import requests

sys.path.append("/")
from core.base.settings import settings                       # pylint: disable=wrong-import-position


# ─────────────────── constants ────────────────────────────
VAULT_ADDR = f"http://{settings.VAULT_HOST}:{settings.VAULT_PORT}"

SECRETS_DIR      = Path("/vault/secrets")
ROOT_TOKEN_JSON  = SECRETS_DIR / "root_vault_token.json"

SCHEMA: Dict[str, Dict] = {
    "secrets": {
        "database": {"user": "speculorg", "pass": "speculpwd"},
        "rabbitmq": {"user": "guest",      "pass": "guest"},
        "keycloak": {"user": "admin",      "pass": "admin"},
    },
    "policies": {
        # name : policy-string
        "read-db": """
            path "secret/data/database" {
            capabilities = ["read"]
            }
            """,
    },
    "approles": {
        # name : { "policies": ["read-db"], "secret_id_ttl": "0s", ... }
        "db-role": {"policies": ["read-db"], "secret_id_ttl": "0s"},
    },
}


# ─────────────────── logging ────────────────────────────
logger = logging.getLogger("vault")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
if not logger.handlers:
    logger.addHandler(handler)


def _fatal(msg: str) -> None:
    logger.error(msg)
    sys.exit(1)


# ──────────────────── helpers ─────────────────────────────
def _wait_vault(timeout: int = 30) -> Dict:
    url = f"{VAULT_ADDR}/v1/sys/health"
    end = time.time() + timeout
    while time.time() < end:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code in (200, 429, 501, 503):
                return r.json() if r.content else {}
        except Exception:
            pass
        time.sleep(1)
    _fatal("Vault not responding")


def _api(method: str, path: str, token: str | None = None, **kw):
    hdr = {"X-Vault-Token": token} if token else {}
    return requests.request(method, f"{VAULT_ADDR}{path}", headers=hdr, timeout=5, **kw)


# ──────────────────── workflow ────────────────────────────
def main() -> None:

    if not SECRETS_DIR.exists():
        logger.info("SECRETS_DIR not exists: create it ...")
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Directory created: %s", SECRETS_DIR)

    # ensure vault reachable
    state = _wait_vault()

    # ── init / save keys ───────────────────────────────
    if not ROOT_TOKEN_JSON.exists():
        if state.get("initialized"):   # keys lost?
            _fatal("Vault already initialised but keys file missing")
        logger.info("Initialising Vault ...")
        res = _api("PUT", "/v1/sys/init", json={"secret_shares": 1, "secret_threshold": 1})
        if res.status_code != 200:
            _fatal("Init error: {res.status_code} {res.text}")
        ROOT_TOKEN_JSON.write_text(res.text)
        logger.info("Keys saved -> %s", ROOT_TOKEN_JSON)

    with ROOT_TOKEN_JSON.open() as f:
        keys = json.load(f)

    root_token = keys["root_token"]
    unseal_key = keys["keys"][0]

    # ── unseal (idempotent) ────────────────────────────
    if state.get("sealed"):
        logger.info("Unsealing ...")
        res = _api("PUT", "/v1/sys/unseal", json={"key": unseal_key})
        if res.status_code != 200:
            _fatal("Unseal error: {res.status_code} {res.text}")

    # ── enable KV v2 if required ───────────────────────
    mounts = _api("GET", "/v1/sys/mounts", token=root_token).json()
    if "secret/" not in mounts:
        logger.info("Enabling KV engine ...")
        _api("POST", "/v1/sys/mounts/secret", token=root_token, json={"type": "kv", "options": {"version": "2"}})

    # ── write secrets ──────────────────────────────────
    for name, data in SCHEMA["secrets"].items():
        path = f"/v1/secret/data/{name}"
        _api("POST", path, token=root_token, json={"data": data})
        logger.info("Secret written -> %s", name)

    # ── policies ───────────────────────────────────────
    for pol, rules in SCHEMA["policies"].items():
        _api("PUT", "/v1/sys/policies/acl/"+pol, token=root_token, json={
            "policy": rules,
            "name": pol,
            "type": "service",
        })
        logger.info("Policy ensured -> %s", pol)

    # ── approles ───────────────────────────────────────
    for role, cfg in SCHEMA["approles"].items():
        _api("POST", f"/v1/auth/approle/role/{role}", token=root_token, json=cfg)
        logger.info("Approle ensured -> %s", role)

    logger.info("OK - init-vault done")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:           # pylint: disable=broad-except
        _fatal(str(exc))
