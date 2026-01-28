from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

import requests

from core._interfaces import IConfigs, IFS, ILogger, IMarkers


def _wait_ready(base_url: str, *, timeout_s: float = 60.0) -> None:
    """Ожидание готовности Consul (leader выбран)."""
    t0 = time.time()
    while True:
        try:
            r = requests.get(f"{base_url}/v1/status/leader", timeout=2.0)
            if r.status_code == 200 and r.text.strip().strip('"'):
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

    2) Минимальные политики + токены сервисов (TERM-1, статичные):
       - consul_token_for_consul
       - consul_token_for_vault
       - consul_token_for_traefik

       Политики (важно):
       - для Vault/Traefik разрешён agent_prefix write (вариант 1),
         чтобы работали TTL регистрации и /v1/agent/check/pass.

    3) Установка agent token для Consul агента (чтобы не было anonymous операций).
       default token НЕ задаём (минимизация поверхности).

    Важно:
    - Маркеры НЕ выставляются здесь (это делает BootstrapPolicy ядра).
    - Функция должна падать, если после выполнения нет обязательных артефактов.
    """
    _ = markers  # выставляет BootstrapPolicy

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

    if log:
        log.info("consul_bootstrap:start", fields={"base": base, "secrets_dir": str(secrets_dir)})

    _wait_ready(base)

    def _load_root_token() -> str:
        if fs.exists(root_token_json):
            return str(fs.read_json(root_token_json).get("SecretID", "")).strip()
        if fs.exists(compat_root_token_json):
            return str(fs.read_json(compat_root_token_json).get("SecretID", "")).strip()
        return ""

    root_token = _load_root_token()

    if not root_token:
        if log:
            log.info("consul_bootstrap:acl_bootstrap", fields={"url": f"{base}/v1/acl/bootstrap"})
        data = _req_json("PUT", f"{base}/v1/acl/bootstrap", ok=(200,), timeout_s=10.0)
        if "SecretID" not in data:
            raise RuntimeError("consul_acl_bootstrap_missing_secretid")
        fs.write_json_atomic(root_token_json, data)
        fs.write_json_atomic(compat_root_token_json, data)
        root_token = str(data["SecretID"]).strip()

    if not root_token:
        raise RuntimeError("consul_acl_bootstrap_missing_root_token")

    if log:
        log.info("consul_bootstrap:root_token_ok", fields={"stored": True})

    # --- policies (upsert) ---

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
            "Description": "Vault storage + TTL registration policy (TERM-1)",
            "Rules": (
                'key_prefix "vault/" { policy = "write" }\n'
                'service "vault" { policy = "write" }\n'
                'service_prefix "" { policy = "read" }\n'
                'node_prefix "" { policy = "read" }\n'
                'agent_prefix "" { policy = "write" }\n'
                'session_prefix "" { policy = "write" }\n'
            ),
        },
        "traefik-policy": {
            "Description": "Traefik catalog read + TTL registration policy (TERM-1)",
            "Rules": (
                'service "traefik" { policy = "write" }\n'
                'service_prefix "" { policy = "read" }\n'
                'node_prefix "" { policy = "read" }\n'
                'agent_prefix "" { policy = "write" }\n'
                'session_prefix "" { policy = "write" }\n'
                'key_prefix "" { policy = "read" }\n'
            ),
        },
    }

    def _policy_upsert(name: str, desc: str, rules: str) -> None:
        url_by_name = f"{base}/v1/acl/policy/name/{name}"
        st = _req_status("GET", url_by_name, token=root_token, timeout_s=5.0)
        if st == 404:
            _req_json(
                "PUT",
                f"{base}/v1/acl/policy",
                token=root_token,
                payload={"Name": name, "Description": desc, "Rules": rules},
                ok=(200,),
                timeout_s=10.0,
            )
            return

        if st != 200:
            raise RuntimeError(f"consul_policy_check_unexpected:{name}:{st}")

        existing = _req_json("GET", url_by_name, token=root_token, ok=(200,), timeout_s=5.0)
        policy_id = str(existing.get("ID", "")).strip()
        if not policy_id:
            raise RuntimeError(f"consul_policy_missing_id:{name}")

        ex_desc = str(existing.get("Description", "")).strip()
        ex_rules = str(existing.get("Rules", "")).strip()

        if ex_desc == desc.strip() and ex_rules == rules.strip():
            return

        _req_json(
            "PUT",
            f"{base}/v1/acl/policy/{policy_id}",
            token=root_token,
            payload={"ID": policy_id, "Name": name, "Description": desc, "Rules": rules},
            ok=(200,),
            timeout_s=10.0,
        )

    for name, p in policies.items():
        if log:
            log.info("consul_bootstrap:policy_upsert", fields={"policy": name})
        _policy_upsert(name, p["Description"], p["Rules"])

    # --- tokens (ensure on disk) ---

    def _ensure_token(kind: str, policy_name: str) -> None:
        path = token_files[kind]
        if fs.exists(path) and fs.read_text(path).strip():
            if log:
                log.info("consul_bootstrap:token_exists", fields={"kind": kind, "file": str(path)})
            return

        if log:
            log.info("consul_bootstrap:token_create", fields={"kind": kind, "policy": policy_name})

        created = _req_json(
            "PUT",
            f"{base}/v1/acl/token",
            token=root_token,
            payload={"Description": f"{kind} token", "Policies": [{"Name": policy_name}], "Local": True},
            ok=(200,),
            timeout_s=10.0,
        )
        secret = str(created.get("SecretID", "")).strip()
        if not secret:
            raise RuntimeError(f"consul_token_create_missing_secretid:{kind}")
        fs.write_text_atomic(path, secret + "\n")

    _ensure_token("consul", "consul-policy")
    _ensure_token("vault", "vault-policy")
    _ensure_token("traefik", "traefik-policy")

    for p in token_files.values():
        if not fs.exists(p) or not fs.read_text(p).strip():
            raise RuntimeError(f"missing_token_file:{p.name}")

    # --- set agent token to avoid anonymous internal calls ---

    consul_token = fs.read_text(token_files["consul"]).strip()
    if not consul_token:
        raise RuntimeError("empty_consul_agent_token")

    if log:
        log.info("consul_bootstrap:set_agent_token")

    _req_json(
        "PUT",
        f"{base}/v1/agent/token/agent",
        token=root_token,
        payload={"Token": consul_token},
        ok=(200,),
        timeout_s=5.0,
    )

    if log:
        log.info("consul_bootstrap:done")
