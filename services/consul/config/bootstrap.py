from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

import requests

from core._interfaces import IConfigs, IFS, ILogger, IMarkers


def _wait_ready(base_url: str, *, timeout_s: float = 60.0, log: ILogger | None = None) -> None:
    """Ожидание готовности Consul (leader выбран)."""
    t0 = time.time()
    while True:
        try:
            r = requests.get(f"{base_url}/v1/status/leader", timeout=2.0)
            if r.status_code == 200 and r.text.strip().strip('"'):
                if log is not None:
                    log.info("consul_bootstrap:ready", fields={"leader": r.text.strip().strip('"')})
                return
        except Exception:
            pass

        if time.time() - t0 >= timeout_s:
            raise RuntimeError("consul_not_ready")

        time.sleep(0.5)


def _req_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    ok: tuple[int, ...] = (200,),
    timeout_s: float = 5.0,
) -> dict[str, Any]:
    headers: dict[str, str] = {}
    if token:
        headers["X-Consul-Token"] = token
    r = requests.request(method, url, headers=headers, json=payload, timeout=timeout_s)
    if r.status_code not in ok:
        raise RuntimeError(f"consul_http_error:{r.status_code}:{(r.text or '')[:256]}")
    return r.json() if r.text else {}


def _req_status(method: str, url: str, *, token: str | None = None, timeout_s: float = 5.0) -> int:
    headers: dict[str, str] = {}
    if token:
        headers["X-Consul-Token"] = token
    r = requests.request(method, url, headers=headers, timeout=timeout_s)
    return r.status_code


def consul_bootstrap(*, cfg: IConfigs, fs: IFS, markers: IMarkers, log: Optional[ILogger] = None) -> None:
    """
    TERM-1 bootstrap для Consul (идемпотентно):

    1) ACL bootstrap (root management token) и сохранение на диск:
       - FS_SECRETS_DIR/root_consul_token.json
       - FS_SECRETS_DIR/consul_acl_bootstrap_token.json (совместимость)

    2) Минимальные политики + токены сервисов (статичные на TERM-1):
       - consul_token_for_consul
       - consul_token_for_vault
       - consul_token_for_traefik

    3) Установка agent/default токена для Consul-агента (чтобы не было anonymous-операций).

    Важно:
    - Маркеры здесь НЕ выставляются (это делает BootstrapPolicy ядра).
    - Функция обязана падать с исключением, если после выполнения нет обязательных артефактов.
    """
    _ = markers  # маркеры управляются ядром

    def _log(msg: str, **fields) -> None:
        if log is None:
            return
        log.info(msg, fields=fields or None)

    secrets_dir = Path(str(cfg.get("FS_SECRETS_DIR", "/fs/terminal/secrets")))
    fs.ensure_dir(secrets_dir)

    root_token_json = secrets_dir / "root_consul_token.json"
    compat_root_token_json = secrets_dir / "consul_acl_bootstrap_token.json"

    token_files: dict[str, Path] = {
        "consul": secrets_dir / "consul_token_for_consul",
        "vault": secrets_dir / "consul_token_for_vault",
        "traefik": secrets_dir / "consul_token_for_traefik",
    }

    consul_http_port = int(cfg.get("CONSUL_HTTP_PORT", 8500))
    base = f"http://127.0.0.1:{consul_http_port}"
    _log("consul_bootstrap:start", base=base, secrets_dir=str(secrets_dir))

    _wait_ready(base, log=log)

    def _load_root_token() -> str:
        if fs.exists(root_token_json):
            return str(fs.read_json(root_token_json).get("SecretID", "")).strip()
        if fs.exists(compat_root_token_json):
            return str(fs.read_json(compat_root_token_json).get("SecretID", "")).strip()
        return ""

    root_token = _load_root_token()

    if not root_token:
        _log("consul_bootstrap:acl_bootstrap:request")
        data = _req_json("PUT", f"{base}/v1/acl/bootstrap", ok=(200,), timeout_s=10.0)
        if "SecretID" not in data:
            raise RuntimeError("consul_acl_bootstrap_missing_secretid")
        fs.write_json_atomic(root_token_json, data)
        fs.write_json_atomic(compat_root_token_json, data)
        root_token = str(data["SecretID"]).strip()
        _log("consul_bootstrap:acl_bootstrap:ok", saved=str(root_token_json))

    if not root_token:
        raise RuntimeError("consul_acl_bootstrap_missing_root_token")

    # --- policies (upsert) ---
    # TERM-1 Variant 1: Vault/Traefik need agent write to register+TTL.
    policies: dict[str, dict[str, str]] = {
        "consul-policy": {
            "Description": "Consul agent policy (TERM-1)",
            "Rules": (
                'node_prefix "" { policy = "write" }\n'
                'service_prefix "" { policy = "write" }\n'
                'agent_prefix "" { policy = "write" }\n'
                'session_prefix "" { policy = "write" }\n'
                'key_prefix "" { policy = "read" }\n'
            ),
        },
        "vault-policy": {
            "Description": "Vault storage + registration policy (TERM-1)",
            "Rules": (
                'key_prefix "vault/" { policy = "write" }\n'
                'service "vault" { policy = "write" }\n'
                'agent_prefix "" { policy = "write" }\n'
                'session_prefix "" { policy = "write" }\n'
                'node_prefix "" { policy = "read" }\n'
                'service_prefix "" { policy = "read" }\n'
            ),
        },
        "traefik-policy": {
            "Description": "Traefik catalog read + registration policy (TERM-1)",
            "Rules": (
                'service_prefix "" { policy = "read" }\n'
                'node_prefix "" { policy = "read" }\n'
                'key_prefix "" { policy = "read" }\n'
                'agent_prefix "" { policy = "write" }\n'
                'service "traefik" { policy = "write" }\n'
                'session_prefix "" { policy = "write" }\n'
            ),
        },
    }

    def _policy_upsert(name: str, desc: str, rules: str) -> None:
        url_by_name = f"{base}/v1/acl/policy/name/{name}"
        st = _req_status("GET", url_by_name, token=root_token, timeout_s=5.0)
        if st == 404:
            _log("consul_bootstrap:policy:create", name=name)
            _req_json(
                "PUT",
                f"{base}/v1/acl/policy",
                token=root_token,
                payload={"Name": name, "Description": desc, "Rules": rules},
                ok=(200,),
                timeout_s=10.0,
            )
            return

        if st == 200:
            # update by ID (Consul API needs policy ID)
            p = _req_json("GET", url_by_name, token=root_token, ok=(200,), timeout_s=5.0)
            pid = str(p.get("ID", "")).strip()
            if not pid:
                raise RuntimeError(f"consul_policy_missing_id:{name}")
            _log("consul_bootstrap:policy:update", name=name, id=pid)
            _req_json(
                "PUT",
                f"{base}/v1/acl/policy/{pid}",
                token=root_token,
                payload={"Name": name, "Description": desc, "Rules": rules},
                ok=(200,),
                timeout_s=10.0,
            )
            return

        raise RuntimeError(f"consul_policy_unexpected_status:{name}:{st}")

    for pname, meta in policies.items():
        _policy_upsert(pname, meta["Description"], meta["Rules"])

    # --- tokens (create if missing) ---
    def _ensure_token(file_path: Path, *, desc: str, policy_name: str) -> str:
        if fs.exists(file_path) and fs.read_text(file_path).strip():
            tok = fs.read_text(file_path).strip()
            _log("consul_bootstrap:token:exists", file=str(file_path), policy=policy_name)
            return tok

        _log("consul_bootstrap:token:create", file=str(file_path), policy=policy_name)
        data = _req_json(
            "PUT",
            f"{base}/v1/acl/token",
            token=root_token,
            payload={
                "Description": desc,
                "Policies": [{"Name": policy_name}],
            },
            ok=(200,),
            timeout_s=10.0,
        )
        secret = str(data.get("SecretID", "")).strip()
        if not secret:
            raise RuntimeError(f"consul_token_create_failed:{file_path.name}")

        fs.write_text_atomic(file_path, secret + "\n")
        return secret

    consul_token = _ensure_token(token_files["consul"], desc="TERM-1: Consul agent token", policy_name="consul-policy")
    _ensure_token(token_files["vault"], desc="TERM-1: Vault token", policy_name="vault-policy")
    _ensure_token(token_files["traefik"], desc="TERM-1: Traefik token", policy_name="traefik-policy")

    # --- set agent/default token ---
    _log("consul_bootstrap:agent_tokens:set")
    _req_json(
        "PUT",
        f"{base}/v1/agent/token/agent",
        token=root_token,
        payload={"Token": consul_token},
        ok=(200,),
        timeout_s=10.0,
    )
    _req_json(
        "PUT",
        f"{base}/v1/agent/token/default",
        token=root_token,
        payload={"Token": consul_token},
        ok=(200,),
        timeout_s=10.0,
    )

    # --- verify artifacts ---
    required = [root_token_json, compat_root_token_json, *token_files.values()]
    for p in required:
        if not fs.exists(p):
            raise RuntimeError(f"missing_required_artifact:{p.name}")
        if not fs.read_text(p).strip() and p.suffix != ".json":
            raise RuntimeError(f"empty_required_artifact:{p.name}")

    _log("consul_bootstrap:ok", artifacts=[str(p) for p in required])
