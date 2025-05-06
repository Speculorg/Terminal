#!/usr/bin/env python3
import os
import time
import json
import sys
import requests

VAULT_ADDR = os.getenv("VAULT_ADDR", "http://vault.service:8200")
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


def log(msg):
    print(f"[VAULT-INIT] {msg}", flush=True)


def fatal(msg):
    print(f"[VAULT-INIT] ❌ {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def wait_for_vault(timeout=60):
    log("Waiting for Vault to be available...")
    for _ in range(timeout):
        try:
            res = requests.get(f"{VAULT_ADDR}/v1/sys/health", timeout=2)
            if res.status_code in (200, 429, 501, 503):
                log(f"Vault status: {res.status_code}")
                return
        except Exception:
            pass
        time.sleep(1)
    fatal("Vault not responding")


def is_initialized():
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
        log("Unseal ok.")
    except Exception as e:
        fatal(f"Unseal error: {e}")


def login_root():
    try:
        with open(VAULT_KEYS_PATH) as f:
            keys = json.load(f)
        token = keys["root_token"]
        return {"X-Vault-Token": token}
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
    print(json.dumps(SECRET_DATA, indent=2), flush=True)
    for name, secret in SECRET_DATA.items():
        if not secret or any(v is None for v in secret.values()):
            log(f"⚠️ Skipping secret {name}, has empty values: {secret}")
            continue
        log(f"Putting secret: {name} ...")
        res = requests.post(f"{VAULT_ADDR}/v1/secret/data/{name}", headers=headers, json={"data": secret})
        if res.status_code not in (200, 204):
            fatal(f"Failed to store {name}: {res.status_code} {res.text}")
        log(f"✓ Secret {name} written.")


def main():
    log("Running Vault initializer...")
    wait_for_vault()

    # Шаг 1: проверка init-флага
    if not os.path.exists(VAULT_KEYS_PATH):
        if not is_initialized():
            init_vault()
        else:
            fatal("Vault is initialized but key file is missing. Please investigate.")
    else:
        log("Vault already initialized.")

    # Шаг 2: unseal
    unseal()

    # Шаг 3: авторизация
    headers = login_root()

    # Шаг 4: монтирование KV, если требуется
    mount_secret_if_needed(headers)

    # Шаг 5: загрузка секретов
    put_secrets(headers)

    log("Vault init complete.")

    sys.exit(0)


if __name__ == "__main__":
    main()
