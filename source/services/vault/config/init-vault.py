# source\services\vault\config\init-vault.py

import os
import time
import json
import sys
import requests
import logging


VAULT_HOST = os.getenv("VAULT_HOST", "vault")
VAULT_PORT = os.getenv("VAULT_PORT", "8200")
VAULT_ADDR = f"http://{VAULT_HOST}:{VAULT_PORT}"

VAULT_KEYS_PATH = "/vault/config/.vault_keys.json"

SECRET_DATA = {
    "postgres": {
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
        "db": os.getenv("POSTGRES_DB"),
        "port": os.getenv("POSTGRES_PORT")
    },
    "redis": {
        "port": os.getenv("REDIS_PORT")
    },
    "rabbitmq": {
        "user": os.getenv("RABBITMQ_DEFAULT_USER"),
        "password": os.getenv("RABBITMQ_DEFAULT_PASS"),
        "port": os.getenv("RABBITMQ_PORT"),
        "management_port": os.getenv("RABBITMQ_MANAGEMENT_PORT")
    }
}

# === LOGGING SETUP ===
logger = logging.getLogger("vault")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
if not logger.handlers:
    logger.addHandler(handler)


def log(msg): logger.info(msg)
def warn(msg): logger.warning(msg)
def fatal(msg): logger.error(msg); sys.exit(1)


def wait_for_vault(timeout=60):
    log("Waiting for Vault to be available...")
    for _ in range(timeout):
        try:
            res = requests.get(f"{VAULT_ADDR}/v1/sys/health", timeout=2)
            if res.status_code == 200:
                # Vault initialized, unsealed, ready
                log("Vault is unsealed and active.")
                return
            elif res.status_code == 503:
                # Vault is sealed but initialized
                body = res.json()
                if body.get("initialized") and body.get("sealed"):
                    log("Vault is sealed but initialized.")
                    return
                elif not body.get("initialized"):
                    log("Vault is not yet initialized.")
                    return
                else:
                    log(f"Vault 503 response: {body}")
            elif res.status_code == 429:
                log("Vault is unsealed and active, but in standby (429).")
                return
            elif res.status_code == 501:
                log("Vault not initialized (501).")
                return
            else:
                log(f"Unexpected status: {res.status_code}")
        except Exception as e:
            warn(f"Vault not reachable yet: {e}")
        time.sleep(1)
    fatal("Vault not responding after timeout.")


def is_initialized():
    log("Checking if Vault is initialized ...")
    try:
        res = requests.get(f"{VAULT_ADDR}/v1/sys/init")
        return res.json().get("initialized", False)
    except Exception as e:
        fatal(f"Failed to get initialization status: {e}")


def init_vault():
    log("Initializing Vault ...")
    init_data = {
        "secret_shares": 1,
        "secret_threshold": 1
    }
    res = requests.put(f"{VAULT_ADDR}/v1/sys/init", json=init_data)
    if res.status_code != 200:
        fatal(f"Init failed: {res.status_code} {res.text}")
    with open(VAULT_KEYS_PATH, "w") as f:
        f.write(res.text)
    log("Vault initialized and keys saved.")


def unseal():
    log("Unsealing Vault ...")
    try:
        with open(VAULT_KEYS_PATH) as f:
            keys = json.load(f)
        res = requests.put(f"{VAULT_ADDR}/v1/sys/unseal", json={"key": keys["keys"][0]})
        if res.status_code != 200:
            fatal(f"Unseal failed: {res.status_code} {res.text}")
        log("Unseal OK.")
    except Exception as e:
        fatal(f"Unseal error: {e}")


def login_root():
    log("Login root ...")
    try:
        with open(VAULT_KEYS_PATH) as f:
            keys = json.load(f)
        log("Login root OK.")
        return {"X-Vault-Token": keys["root_token"]}
    except Exception as e:
        fatal(f"Cannot load root token: {e}")


def mount_secret_if_needed(headers):
    log("Enabling KV secrets engine at /secret ...")
    res = requests.get(f"{VAULT_ADDR}/v1/sys/mounts", headers=headers)
    if res.status_code != 200:
        fatal(f"Cannot list mounts: {res.status_code} {res.text}")
    if "secret/" in res.json():
        log("KV already mounted.")
        return
    res = requests.post(f"{VAULT_ADDR}/v1/sys/mounts/secret", headers=headers, json={"type": "kv"})
    if res.status_code != 204:
        fatal(f"Mount failed: {res.status_code} {res.text}")
    log("KV mounted.")


def put_secrets(headers):
    log("Putting secrets ...")
    for name, secret in SECRET_DATA.items():
        if not secret or any(v is None for v in secret.values()):
            warn(f"⚠️ Skipping secret {name}, has empty values: {secret}")
            continue
        log(f"Putting secret: {name} ...")
        res = requests.post(f"{VAULT_ADDR}/v1/secret/data/{name}", headers=headers, json={"data": secret})
        if res.status_code not in (200, 204):
            fatal(f"Failed to store {name}: {res.status_code} {res.text}")
        log(f"✓ Secret {name} written.")


def main():
    log("Running Vault initializer...")
    wait_for_vault()

    if not os.path.exists(VAULT_KEYS_PATH):
        if not is_initialized():
            init_vault()
        else:
            fatal("Vault is initialized but key file is missing. Please investigate.")
    else:
        log("Vault already initialized.")

    unseal()
    headers = login_root()
    mount_secret_if_needed(headers)
    put_secrets(headers)

    log("Vault init complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()
