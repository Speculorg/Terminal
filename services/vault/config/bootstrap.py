from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import requests

from core._interfaces import IConfigs, IFS, ILogger, IMarkers


def _http_get_json(url: str, *, headers: Optional[Dict[str, str]] = None, timeout_ms: int = 2000) -> Dict[str, Any]:
    r = requests.get(url, headers=headers or {}, timeout=max(0.2, timeout_ms / 1000.0))
    if r.status_code >= 300:
        raise RuntimeError(f"http_error:{r.status_code}:{(r.text or '')[:256]}")
    return r.json() if r.text else {}


def _http_put_json(url: str, payload: Dict[str, Any], *, headers: Optional[Dict[str, str]] = None, timeout_ms: int = 2000) -> Dict[str, Any]:
    r = requests.put(url, json=payload, headers=headers or {}, timeout=max(0.2, timeout_ms / 1000.0))
    if r.status_code >= 300:
        raise RuntimeError(f"http_error:{r.status_code}:{(r.text or '')[:256]}")
    return r.json() if r.text else {}


def _http_post_json(url: str, payload: Dict[str, Any], *, headers: Optional[Dict[str, str]] = None, timeout_ms: int = 2000) -> Dict[str, Any]:
    r = requests.post(url, json=payload, headers=headers or {}, timeout=max(0.2, timeout_ms / 1000.0))
    if r.status_code >= 300:
        raise RuntimeError(f"http_error:{r.status_code}:{(r.text or '')[:256]}")
    return r.json() if r.text else {}


def _vault_headers(token: str) -> Dict[str, str]:
    return {"X-Vault-Token": token}


def vault_bootstrap(*, cfg: IConfigs, fs: IFS, markers: IMarkers, log: Optional[ILogger] = None) -> None:
    """
    TERM-1 bootstrap для Vault:
    - init (1 share / 1 threshold) и сохранение root token + unseal key(s) в secrets_dir
    - unseal (если sealed)
    - включение PKI root и генерация CA
    - выпуск initial leaf certs (vault, consul) и запись PEM в certs_dir
    - выставляет: vault_init.done, vault_initial_pem.done

    Принцип: строго идемпотентно, без ручных шагов.
    """
    if markers.has("vault_init.done") and markers.has("vault_initial_pem.done"):
        return

    secrets_dir = Path(str(cfg.get("FS_SECRETS_DIR", "/fs/terminal/secrets")))
    certs_dir = Path(str(cfg.get("FS_CERTS_DIR", "/fs/terminal/certs")))
    fs.ensure_dir(secrets_dir)
    fs.ensure_dir(certs_dir)

    init_file = secrets_dir / "vault_init.json"

    base = f"http://127.0.0.1:{int(cfg.get('VAULT_HTTP_PORT', 8200) or 8200)}"

    # 1) init (idempotent)
    init_status = _http_get_json(f"{base}/v1/sys/init")
    initialized = bool(init_status.get("initialized", False))

    init_doc: Optional[Dict[str, Any]] = fs.read_json(str(init_file)) if fs.exists(str(init_file)) else None

    if not initialized:
        # минимализм TERM-1: 1 ключ unseal
        resp = _http_put_json(
            f"{base}/v1/sys/init",
            {"secret_shares": 1, "secret_threshold": 1},
            timeout_ms=4000,
        )
        fs.write_json_atomic(str(init_file), resp)
        init_doc = resp

    if not init_doc:
        # если Vault уже initialized, но файла нет — это несходимость TERM-1 (нужно восстановить вручную)
        raise RuntimeError("vault_init_file_missing")

    root_token = str(init_doc.get("root_token") or "")
    keys = init_doc.get("keys") or init_doc.get("keys_base64") or []
    if not root_token or not keys:
        raise RuntimeError("vault_init_artifacts_invalid")

    markers.set("vault_init.done")

    # 2) unseal (idempotent)
    seal = _http_get_json(f"{base}/v1/sys/seal-status")
    if bool(seal.get("sealed", True)):
        key = str(keys[0])
        _http_post_json(f"{base}/v1/sys/unseal", {"key": key}, timeout_ms=3000)

    # 3) PKI root (idempotent)
    pki_path = str(cfg.get("VAULT_PKI_ROOT_PATH", "pki-root"))
    role_name = str(cfg.get("VAULT_PKI_ROLE", "terminal-leaf"))
    domain_root = str(cfg.get("DOMAIN_ROOT", "terminal.local"))
    ca_cn = str(cfg.get("TLS_CA_CN", f"terminal-ca.{domain_root}"))

    hdr = _vault_headers(root_token)

    # enable pki (ignore if already enabled)
    try:
        _http_post_json(f"{base}/v1/sys/mounts/{pki_path}", {"type": "pki"}, headers=hdr, timeout_ms=4000)
    except Exception:
        pass

    # tune ttl (ignore errors)
    try:
        _http_post_json(
            f"{base}/v1/sys/mounts/{pki_path}/tune",
            {"max_lease_ttl": "8760h"},
            headers=hdr,
            timeout_ms=4000,
        )
    except Exception:
        pass

    # generate root CA only if cert file missing
    ca_file = certs_dir / "ca.crt"
    if not fs.exists(str(ca_file)):
        resp = _http_post_json(
            f"{base}/v1/{pki_path}/root/generate/internal",
            {"common_name": ca_cn, "ttl": "8760h"},
            headers=hdr,
            timeout_ms=6000,
        )
        cert = str(resp.get("data", {}).get("certificate") or "")
        if not cert:
            raise RuntimeError("vault_pki_root_generate_failed")
        fs.write_text_atomic(str(ca_file), cert + "\n")

    # role (upsert)
    _http_post_json(
        f"{base}/v1/{pki_path}/roles/{role_name}",
        {
            "allow_any_name": True,
            "max_ttl": "24h",
        },
        headers=hdr,
        timeout_ms=4000,
    )

    # issue initial certs
    def issue_leaf(name: str) -> None:
        cert_file = certs_dir / f"{name}.crt"
        key_file = certs_dir / f"{name}.key"
        if fs.exists(str(cert_file)) and fs.exists(str(key_file)):
            return

        resp = _http_post_json(
            f"{base}/v1/{pki_path}/issue/{role_name}",
            {
                "common_name": name,
                "ttl": "24h",
            },
            headers=hdr,
            timeout_ms=6000,
        )
        data = resp.get("data", {})
        cert = str(data.get("certificate") or "")
        key = str(data.get("private_key") or "")
        if not cert or not key:
            raise RuntimeError(f"vault_pki_issue_failed:{name}")

        fs.write_text_atomic(str(cert_file), cert + "\n")
        fs.write_text_atomic(str(key_file), key + "\n")

    issue_leaf("vault")
    issue_leaf("consul")

    markers.set("vault_initial_pem.done")

    if log is not None:
        try:
            log.event("vault.bootstrap.ok", fields={"pki_path": pki_path, "certs_dir": str(certs_dir)})
        except Exception:
            pass
