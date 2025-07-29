# source\services\vault\config\init-vault.py


from __future__ import annotations
import json
import logging
import sys
import time
import requests
from pathlib import Path
from typing import Final
sys.path.append("/")
from core.base.settings import settings # global config


# --------------------------------------------------------------------------- #
#                                   Constants                                 #
# --------------------------------------------------------------------------- #
VAULT_HOST:           Final[str] = settings.VAULT_HOST
VAULT_PORT:           Final[int] = settings.VAULT_PORT

CERTS_DIR:            Final[Path] = Path("/certs")
SECRETS_DIR:          Final[Path] = Path("/vault/secrets")
ROOT_TOKEN_JSON:      Final[Path] = SECRETS_DIR / "root_vault_token.json"

TLS_ENABLED = all((CERTS_DIR / f).exists() for f in ("vault.crt", "vault.key", "ca.crt"))
VAULT_ADDR = f"{'https' if TLS_ENABLED else 'http'}://{VAULT_HOST}:{VAULT_PORT}"

SESSION = requests.Session()
SESSION.verify = str(CERTS_DIR / "ca.crt") if TLS_ENABLED else False

WAIT_READY_SEC:       Final[int] = 30

PKI_ROOT_TTL:         Final[str] = "87600h"
PKI_ROLE_MAX_TTL:     Final[str] = "720h"
DOMAIN_ROOT:          Final[str] = "speculorg.local"

LEAF_SVCS: Final[dict[str, dict[str, str]]] = {
    "consul":  {"common_name": f"consul.{DOMAIN_ROOT}",  "alt_names": "server.dc-1.consul,consul,localhost"},
    "vault":   {"common_name": f"vault.{DOMAIN_ROOT}",   "alt_names": "vault,localhost"},
    "traefik": {"common_name": f"traefik.{DOMAIN_ROOT}", "alt_names": "traefik,localhost"},
}

SECRETS_KV: Final[dict[str, dict[str, str]]] = {
    "database": {"user": "speculorg", "pass": "speculpwd"},
    "rabbitmq": {"user": "guest",     "pass": "guest"},
    "keycloak": {"user": "admin",     "pass": "admin"},
}

POLICIES: Final[dict[str, str]] = {
    "read-db": """
        path "secret/data/database" {
          capabilities = ["read"]
        }
    """,
}

APPROLES: Final[dict[str, dict]] = {
    "db-role": {"policies": ["read-db"], "secret_id_ttl": "0s"},
}


# --------------------------------------------------------------------------- #
#                                   Logging                                   #
# --------------------------------------------------------------------------- #
logger = logging.getLogger("vault")
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
def wait_for_ready(timeout: int = WAIT_READY_SEC) -> dict:
    url = f"{VAULT_ADDR}/v1/sys/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = SESSION.get(url, timeout=3)
            if r.status_code in (200, 429, 501, 503):
                return r.json() if r.content else {}
        except requests.RequestException:
            pass
        time.sleep(1)
    _fatal("Vault health endpoint not reachable within %s s", timeout)


def _api(method: str, path: str, token: str | None = None, **kw) -> requests.Response:
    headers = {"X-Vault-Token": token} if token else {}
    return SESSION.request(method, f"{VAULT_ADDR}{path}", headers=headers, timeout=10, **kw)


def write_file(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o600)
    logger.info("File saved → %s", path)


# --------------------------------------------------------------------------- #
#                                PKI helpers                                  #
# --------------------------------------------------------------------------- #
def ensure_pki(root_token: str) -> None:
    mounts = _api("GET", "/v1/sys/mounts", token=root_token).json()
    if "pki/" not in mounts:
        logger.info("Enabling PKI secrets engine")
        _api("POST", "/v1/sys/mounts/pki", token=root_token, json={"type": "pki"})

    # root CA
    ca_path = CERTS_DIR / "ca.crt"
    if not ca_path.exists():
        logger.info("Generating root CA")
        res = _api(
            "POST",
            "/v1/pki/root/generate/internal",
            token=root_token,
            json={"common_name": DOMAIN_ROOT, "ttl": PKI_ROOT_TTL},
        )
        res.raise_for_status()
        write_file(ca_path, res.json()["data"]["certificate"])

        _api(
            "POST",
            "/v1/pki/config/urls",
            token=root_token,
            json={
                "issuing_certificates": f"{VAULT_ADDR}/v1/pki/ca",
                "crl_distribution_points": f"{VAULT_ADDR}/v1/pki/crl",
            },
        )

    # role
    _api(
        "POST",
        "/v1/pki/roles/internal",
        token=root_token,
        json={
            "allowed_domains": f"{DOMAIN_ROOT},consul,vault,traefik,localhost",
            "allow_subdomains": True,
            "allow_bare_domains": True,
            "allow_glob_domains": True,
            "max_ttl": PKI_ROLE_MAX_TTL,
        },
    )

    # leaf certificates
    for name, params in LEAF_SVCS.items():
        crt, key = CERTS_DIR / f"{name}.crt", CERTS_DIR / f"{name}.key"
        if crt.exists() and key.exists():
            logger.info("Cert for %s already exists - skip", name)
            continue

        logger.info("Issuing certificate for %s", name)
        res = _api("POST", "/v1/pki/issue/internal", token=root_token, json=params)
        res.raise_for_status()
        data = res.json()["data"]
        write_file(crt, data["certificate"])
        write_file(key, data["private_key"])


# --------------------------------------------------------------------------- #
#                                   Main                                      #
# --------------------------------------------------------------------------- #
def main() -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    CERTS_DIR.mkdir(parents=True, exist_ok=True)

    state = wait_for_ready()

    # ---------------- init ----------------
    if not ROOT_TOKEN_JSON.exists():
        if state.get("initialized"):
            _fatal("Vault already initialised but root token file missing")

        logger.info("Initialising Vault (1/1)")
        res = _api("PUT", "/v1/sys/init", json={"secret_shares": 1, "secret_threshold": 1})
        res.raise_for_status()
        write_file(ROOT_TOKEN_JSON, res.text)
        state = res.json()

    # keys
    keys = json.loads(ROOT_TOKEN_JSON.read_text())
    root_token = keys["root_token"]
    unseal_key = keys["keys"][0]

    # ---------------- unseal ----------------
    if state.get("sealed", True):
        logger.info("Unsealing Vault")
        _api("PUT", "/v1/sys/unseal", json={"key": unseal_key})

    # ---------------- KV engine ----------------
    mounts = _api("GET", "/v1/sys/mounts", token=root_token).json()
    if "secret/" not in mounts:
        logger.info("Enabling KV v2 at secret/")
        _api(
            "POST",
            "/v1/sys/mounts/secret",
            token=root_token,
            json={"type": "kv", "options": {"version": "2"}},
        )

    # ---------------- secrets ----------------
    for path, data in SECRETS_KV.items():
        _api("POST", f"/v1/secret/data/{path}", token=root_token, json={"data": data})
        logger.info("Secret %s stored", path)

    # ---------------- policies ----------------
    policy_resp = _api("GET", "/v1/sys/policies/acl", token=root_token)
    policy_dict = policy_resp.json() if policy_resp.ok else {}
    existing_policies = set(policy_dict.keys()) if isinstance(policy_dict, dict) else set()

    for name, rules in POLICIES.items():
        if name in existing_policies:
            logger.info("Policy %s already exists - skip", name)
            continue
        _api(
            "PUT",
            f"/v1/sys/policies/acl/{name}",
            token=root_token,
            json={"policy": rules, "type": "service"},
        )
        logger.info("Policy %s created", name)

    # ---------------- AppRoles ----------------
    for role, cfg in APPROLES.items():
        role_resp = _api("GET", f"/v1/auth/approle/role/{role}", token=root_token)
        if role_resp.ok:
            logger.info("AppRole %s already exists - skip", role)
            continue
        _api("POST", f"/v1/auth/approle/role/{role}", token=root_token, json=cfg)
        logger.info("AppRole %s created", role)

    # ---------------- PKI ----------------
    ensure_pki(root_token)

    logger.info("OK - init-vault done")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pylint: disable=broad-except
        _fatal("Fatal: %s", exc)
