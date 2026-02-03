from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

import requests

from core._interfaces import IConfigs, IFS, ILogger, IMarkers


def _wait_ready(base_url: str, *, timeout_s: float = 60.0, log: ILogger | None = None) -> None:
    """
    Ожидание готовности Consul (leader выбран).

    Важно: ожидание работает в HTTP bootstrap-окне.
    """
    deadline = time.time() + max(1.0, timeout_s)
    delay_s = 0.25

    while True:
        try:
            r = requests.get(f"{base_url}/v1/status/leader", timeout=2.0)
            leader = (r.text or "").strip().strip('"')
            if r.status_code == 200 and leader:
                if log is not None:
                    log.info("consul_bootstrap:ready", fields={"leader": leader})
                return
        except Exception:
            pass

        if time.time() >= deadline:
            raise RuntimeError("consul_not_ready_timeout")

        time.sleep(delay_s)
        delay_s = min(delay_s * 1.2, 1.0)


def _req(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout_s: float = 6.0,
) -> tuple[int, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["X-Consul-Token"] = token
    r = requests.request(method, url, headers=headers, json=payload, timeout=timeout_s)
    return r.status_code, (r.text or "")


def _req_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    ok: tuple[int, ...] = (200,),
    timeout_s: float = 6.0,
) -> dict[str, Any]:
    st, text = _req(method, url, token=token, payload=payload, timeout_s=timeout_s)
    if st not in ok:
        raise RuntimeError(f"consul_http_error:{st}:{text[:256]}")
    if not text.strip():
        return {}
    return json.loads(text)


def _token_self(base_url: str, token: str) -> bool:
    st, _ = _req("GET", f"{base_url}/v1/acl/token/self", token=token, timeout_s=6.0)
    return st == 200


def consul_bootstrap(*, cfg: IConfigs, fs: IFS, markers: IMarkers, log: Optional[ILogger] = None) -> None:
    """
    TERM-1 bootstrap для Consul (идемпотентно, детерминированно).

    Обязательные цели (TERM-1):
    1) ACL bootstrap (management token) и сохранение в cfg.fs.secrets_dir (FS_SECRETS_DIR):
       - root_consul_token.json
       - consul_acl_bootstrap_token.json (legacy-совместимость)

    2) Минимальные политики и токены:
       - consul_token_for_consul  (для agent token)
       - consul_token_for_vault
       - consul_token_for_traefik

    3) Установка только agent token для Consul-агента.
       Default token не трогаем: все клиенты обязаны передавать свой token.

    Маркеры здесь не выставляются (это делает BootstrapPolicy ядра).
    """
    _ = markers  # маркеры выставляет ядро

    def _log(msg: str, **fields: Any) -> None:
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
        for p in (root_token_json, compat_root_token_json):
            if fs.exists(p):
                try:
                    return str(fs.read_json(p).get("SecretID", "")).strip()
                except Exception:
                    return ""
        return ""

    root_token = _load_root_token()

    # Если root token есть, но Consul state (data_dir) был сброшен — токен станет невалидным.
    if root_token and not _token_self(base, root_token):
        _log("consul_bootstrap:root_token:invalid", file=str(root_token_json))
        root_token = ""

    # ACL bootstrap
    if not root_token:
        _log("consul_bootstrap:acl_bootstrap:request")
        st, text = _req("PUT", f"{base}/v1/acl/bootstrap", timeout_s=10.0)

        # 403 = уже bootstrapped, но у нас нет root token на диске -> автоконвергенции нет, нужен оператор.
        if st == 403:
            raise RuntimeError("consul_acl_already_bootstrapped_but_root_token_missing")

        if st != 200:
            raise RuntimeError(f"consul_acl_bootstrap_http_error:{st}:{text[:256]}")

        data = json.loads(text)
        if "SecretID" not in data:
            raise RuntimeError("consul_acl_bootstrap_missing_secretid")

        fs.write_json_atomic(root_token_json, data)
        fs.write_json_atomic(compat_root_token_json, data)

        root_token = str(data["SecretID"]).strip()
        _log("consul_bootstrap:acl_bootstrap:ok", saved=str(root_token_json))

    if not root_token or not _token_self(base, root_token):
        raise RuntimeError("consul_acl_bootstrap_missing_or_invalid_root_token")

    # --- policies (upsert) ---
    # Принцип: минимально достаточные права для TERM-1.
    #
    # consul-policy: agent token (внутренние операции агента + регистрация сервисов).
    # vault-policy: storage (vault/) + session locks + регистрация сервиса "vault".
    # traefik-policy: Consul Catalog read + регистрация сервиса "traefik".
    policies: dict[str, dict[str, str]] = {
        "consul-policy": {
            "Description": "TERM-1: Consul agent policy",
            "Rules": (
                'node_prefix "" { policy = "write" }\n'
                'service_prefix "" { policy = "write" }\n'
                'agent_prefix "" { policy = "write" }\n'
                'session_prefix "" { policy = "write" }\n'
            ),
        },
        "vault-policy": {
            "Description": "TERM-1: Vault policy (Consul storage + registration)",
            "Rules": (
                'key_prefix "vault/" { policy = "write" }\n'
                'session_prefix "" { policy = "write" }\n'
                'service "vault" { policy = "write" }\n'
                'agent_prefix "" { policy = "write" }\n'
            ),
        },
        "traefik-policy": {
            "Description": "TERM-1: Traefik policy (Catalog read + registration)",
            "Rules": (
                'service_prefix "" { policy = "read" }\n'
                'node_prefix "" { policy = "read" }\n'
                'service "traefik" { policy = "write" }\n'
                'agent_prefix "" { policy = "write" }\n'
            ),
        },
    }

    def _policy_upsert(name: str, desc: str, rules: str) -> None:
        url_by_name = f"{base}/v1/acl/policy/name/{name}"
        st, _ = _req("GET", url_by_name, token=root_token, timeout_s=6.0)

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
            p = _req_json("GET", url_by_name, token=root_token, ok=(200,), timeout_s=6.0)
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

    # --- tokens ---
    def _ensure_token(file_path: Path, *, desc: str, policy_name: str) -> str:
        if fs.exists(file_path):
            existing = fs.read_text(file_path).strip()
            if existing and _token_self(base, existing):
                _log("consul_bootstrap:token:valid", file=str(file_path), policy=policy_name)
                return existing

            # файл есть, но токен пустой/битый/невалидный — перегенерируем.
            _log("consul_bootstrap:token:invalid", file=str(file_path), policy=policy_name)

        _log("consul_bootstrap:token:create", file=str(file_path), policy=policy_name)
        data = _req_json(
            "PUT",
            f"{base}/v1/acl/token",
            token=root_token,
            payload={"Description": desc, "Policies": [{"Name": policy_name}]},
            ok=(200,),
            timeout_s=10.0,
        )
        secret = str(data.get("SecretID", "")).strip()
        if not secret:
            raise RuntimeError(f"consul_token_create_failed:{file_path.name}")

        fs.write_text_atomic(file_path, secret + "\n")
        return secret

    consul_token = _ensure_token(
        token_files["consul"],
        desc="TERM-1: Consul agent token",
        policy_name="consul-policy",
    )
    _ensure_token(
        token_files["vault"],
        desc="TERM-1: Vault token",
        policy_name="vault-policy",
    )
    _ensure_token(
        token_files["traefik"],
        desc="TERM-1: Traefik token",
        policy_name="traefik-policy",
    )

    # --- set agent token (ONLY) ---
    _log("consul_bootstrap:agent_token:set", token_file=str(token_files["consul"]))
    _req_json(
        "PUT",
        f"{base}/v1/agent/token/agent",
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

        if p.suffix == ".json":
            continue

        if not fs.read_text(p).strip():
            raise RuntimeError(f"empty_required_artifact:{p.name}")

    _log("consul_bootstrap:ok", artifacts=[str(p) for p in required])
