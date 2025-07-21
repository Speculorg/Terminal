# source\services\vault\config\init-vault.py


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


# ──────────────── constants ─────────────────
SECRETS_DIR = Path("/vault/secrets")
CERTS_DIR   = Path("/certs")

ROOT_TOKEN_JSON = SECRETS_DIR / "root_vault_token.json"

SCHEMA: Dict[str, Dict] = {
    "secrets": {
        "database": {"user": "speculorg", "pass": "speculpwd"},
        "rabbitmq": {"user": "guest",     "pass": "guest"},
        "keycloak": {"user": "admin",     "pass": "admin"},
    },
    "policies": {
        "read-db": '''
            path "secret/data/database" {
              capabilities = ["read"]
            }
        ''',
    },
    "approles": {
        "db-role": {"policies": ["read-db"], "secret_id_ttl": "0s"},
    },
}

PKI_CFG = {
    "root_cn": "speculorg.local",
    "ttl_root": "87600h",
    "role": {
        "allowed_domains": "speculorg.local,consul,dc-1.consul,vault,traefik,localhost",
        "allow_subdomains": True,
        "allow_bare_domains": True,
        "allow_glob_domains": True,
        "max_ttl": "720h",
    },
    "leaf": {
        "consul": {
            "common_name": "consul.speculorg.local",
            "alt_names": "server.dc-1.consul,consul,localhost",
        },
        "vault": {
            "common_name": "vault.speculorg.local",
            "alt_names": "vault,localhost",
        },
        "traefik": {
            "common_name": "traefik.speculorg.local",
            "alt_names": "traefik,localhost",
        },
    },
}


# ──────────────── TLS detection ─────────────
CERTS_OK = (
    (CERTS_DIR / "vault.crt").exists() and 
    (CERTS_DIR / "vault.key").exists() and 
    (CERTS_DIR / "ca.crt").exists()
)
VAULT_SCHEME = "https" if CERTS_OK else "http"
VAULT_PORT   = settings.VAULT_PORT
VAULT_HOST   = settings.VAULT_HOST
VAULT_ADDR   = f"{VAULT_SCHEME}://{VAULT_HOST}:{VAULT_PORT}"

REQUESTS_KWARGS = {}
if CERTS_OK:
    REQUESTS_KWARGS['verify'] = str(CERTS_DIR / "ca.crt")
    # REQUESTS_KWARGS['cert'] = (str(CERTS_DIR / "vault.crt"), str(CERTS_DIR / "vault.key"))
else:
    REQUESTS_KWARGS['verify'] = False


# ──────────────── logging ──────────────────
logger = logging.getLogger("vault-init")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
if not logger.handlers:
    logger.addHandler(handler)

def _fatal(msg: str) -> None:
    logger.error(msg)
    sys.exit(1)


# ──────────────── HTTP helpers ─────────────
def _wait_vault(timeout: int = 60) -> Dict:
    url = f"{VAULT_ADDR}/v1/sys/health"
    end = time.time() + timeout
    while time.time() < end:
        try:
            r = requests.get(url, timeout=3, **REQUESTS_KWARGS)
            if r.status_code in (200, 429, 501, 503):
                return r.json() if r.content else {}
        except Exception:
            pass
        time.sleep(1)
    _fatal("Vault not responding")

def _api(method: str, path: str, token: str | None = None, **kw):
    hdr = {"X-Vault-Token": token} if token else {}
    all_kwargs = dict(REQUESTS_KWARGS)
    all_kwargs.update(kw)
    return requests.request(method, f"{VAULT_ADDR}{path}", headers=hdr, timeout=10, **all_kwargs)


# ──────────────── PKI helpers ──────────────
def _ensure_dirs() -> None:
    for p in (SECRETS_DIR, CERTS_DIR):
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            logger.info("Created dir: %s", p)

def _write_file(path: Path, content: str, mode: int = 0o600) -> None:
    path.write_text(content)
    path.chmod(mode)
    logger.info("File written -> %s", path)

def _setup_pki(root_token: str) -> None:
    """Enable PKI engine, generate CA, role, leaf certs."""
    mounts = _api("GET", "/v1/sys/mounts", token=root_token).json()
    if "pki/" not in mounts:
        logger.info("Enabling PKI engine ...")
        _api("POST", "/v1/sys/mounts/pki",
             token=root_token, json={"type": "pki"})
    else:
        logger.info("PKI engine already enabled, skipping enable step.")

    # Root CA: create once (check by ca.crt file)
    ca_crt_path = CERTS_DIR / "ca.crt"
    if not ca_crt_path.exists():
        logger.info("Generating Root CA ...")
        resp = _api("POST", "/v1/pki/root/generate/internal", token=root_token,
                    json={"common_name": PKI_CFG["root_cn"],
                          "ttl": PKI_CFG["ttl_root"]})
        if resp.status_code != 200:
            _fatal(f"Root CA error: {resp.status_code} {resp.text}")
        _write_file(ca_crt_path, resp.json()["data"]["certificate"])

        # Configure issuing URLs (optional)
        _api("POST", "/v1/pki/config/urls", token=root_token, json={
            "issuing_certificates": f"{VAULT_ADDR}/v1/pki/ca",
            "crl_distribution_points": f"{VAULT_ADDR}/v1/pki/crl",
        })

    # Role
    _api("POST", "/v1/pki/roles/internal", token=root_token,
         json=PKI_CFG["role"])
    logger.info("PKI role 'internal' ensured")

    # Leaf certs
    for name, params in PKI_CFG["leaf"].items():
        crt_path = CERTS_DIR / f"{name}.crt"
        key_path = CERTS_DIR / f"{name}.key"
        if crt_path.exists() and key_path.exists():
            continue
        logger.info("Issuing cert -> %s", name)
        resp = _api("POST", "/v1/pki/issue/internal", token=root_token,
                    json=params)
        if resp.status_code != 200:
            _fatal(f"Leaf cert error ({name}): {resp.status_code} {resp.text}")
        data = resp.json()["data"]
        _write_file(crt_path, data["certificate"])
        _write_file(key_path, data["private_key"])


# ──────────────── main workflow ─────────────
def main() -> None:
    _ensure_dirs()
    state = _wait_vault()

    # 1. init
    if not ROOT_TOKEN_JSON.exists():
        if state.get("initialized"):
            _fatal("Vault already initialised but root token file missing")
        logger.info("Initialising Vault ...")
        res = _api("PUT", "/v1/sys/init",
                   json={"secret_shares": 1, "secret_threshold": 1})
        if res.status_code != 200:
            _fatal(f"Init error: {res.status_code} {res.text}")
        _write_file(ROOT_TOKEN_JSON, res.text)
        logger.info("Keys saved -> %s", ROOT_TOKEN_JSON)

    keys = json.loads(ROOT_TOKEN_JSON.read_text())
    root_token = keys["root_token"]
    unseal_key = keys["keys"][0]

    # 2. unseal
    if state.get("sealed"):
        logger.info("Unsealing ...")
        _api("PUT", "/v1/sys/unseal", json={"key": unseal_key})

    # 3. enable KV v2
    mounts = _api("GET", "/v1/sys/mounts", token=root_token).json()
    if "secret/" not in mounts:
        logger.info("Enabling KV engine ...")
        _api("POST", "/v1/sys/mounts/secret", token=root_token,
             json={"type": "kv", "options": {"version": "2"}})
    else:
        logger.info("KV engine 'secret/' already enabled, skipping enable step.")

    # 4. write secrets
    for name, data in SCHEMA["secrets"].items():
        _api("POST", f"/v1/secret/data/{name}", token=root_token,
             json={"data": data})
        logger.info("Secret written -> %s", name)

    # 5. policies
    for pol, rules in SCHEMA["policies"].items():
        _api("PUT", f"/v1/sys/policies/acl/{pol}", token=root_token,
             json={"policy": rules, "name": pol, "type": "service"})
        logger.info("Policy ensured -> %s", pol)

    # 6. approles
    for role, cfg in SCHEMA["approles"].items():
        _api("POST", f"/v1/auth/approle/role/{role}",
             token=root_token, json=cfg)
        logger.info("AppRole ensured -> %s", role)

    # 7. PKI stuff
    _setup_pki(root_token)

    logger.info("OK - init-vault done")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pylint: disable=broad-except
        _fatal(str(exc))
