from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from core._interfaces import IConfigs, IFS, ILogger, IMarkers


def _vault_headers(token: str) -> Dict[str, str]:
    return {"X-Vault-Token": token}


def _http_get(url: str, *, headers: Optional[Dict[str, str]] = None, timeout_s: float = 2.0) -> requests.Response:
    return requests.get(url, headers=headers or {}, timeout=timeout_s)


def _http_put_json(
    url: str,
    payload: Dict[str, Any],
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout_s: float = 5.0,
    ok: tuple[int, ...] = (200,),
) -> Dict[str, Any]:
    r = requests.put(url, json=payload, headers=headers or {}, timeout=timeout_s)
    if r.status_code not in ok:
        raise RuntimeError(f"vault_http_error:{r.status_code}:{(r.text or '')[:256]}")
    return r.json() if r.text else {}


def _http_post_json(
    url: str,
    payload: Dict[str, Any],
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout_s: float = 5.0,
    ok: tuple[int, ...] = (200, 204),
) -> Dict[str, Any]:
    r = requests.post(url, json=payload, headers=headers or {}, timeout=timeout_s)
    if r.status_code not in ok:
        raise RuntimeError(f"vault_http_error:{r.status_code}:{(r.text or '')[:256]}")
    return r.json() if r.text else {}


def _wait_http_ready(base: str, *, timeout_s: float = 60.0) -> None:
    t0 = time.time()
    while True:
        try:
            r = _http_get(f"{base}/v1/sys/health", timeout_s=2.0)
            if r.status_code in (200, 429, 472, 473, 501, 503) and (r.text or ""):
                return
        except Exception:
            pass

        if time.time() - t0 >= timeout_s:
            raise RuntimeError("vault_not_ready")

        time.sleep(0.5)


def _read_ca_pem(base: str) -> str:
    r = _http_get(f"{base}/v1/pki/ca/pem", timeout_s=5.0)
    if r.status_code != 200:
        raise RuntimeError(f"vault_ca_read_error:{r.status_code}:{(r.text or '')[:128]}")
    return r.text


def _write_pem_bundle(fs: IFS, *, cert_path: Path, key_path: Path, out_path: Path) -> None:
    cert = fs.read_text(cert_path).strip()
    key = fs.read_text(key_path).strip()
    if not cert or not key:
        raise RuntimeError(f"empty_leaf_parts:{out_path.name}")
    fs.write_text_atomic(out_path, cert + "\n" + key + "\n")


def vault_bootstrap(*, cfg: IConfigs, fs: IFS, markers: IMarkers, log: Optional[ILogger] = None) -> None:
    """
    TERM-1 bootstrap для Vault (идемпотентно):

    - init (1/1) и сохранение (root token + unseal key) в FS_SECRETS_DIR/vault_init.json
    - unseal (если sealed)
    - PKI root (CA) + role
    - выпуск initial leaf certs (TTL 24h): vault, consul, traefik
      + запись: ca.crt, <name>.crt, <name>.key, <name>.pem в FS_CERTS_DIR

    Важно:
    - Маркеры НЕ выставляются здесь (это делает BootstrapPolicy ядра).
    - Функция обязана падать с исключением, если после выполнения нет обязательных артефактов.
    """
    _ = markers, log  # не используем напрямую в bootstrap_fn

    secrets_dir = Path(cfg.get("FS_SECRETS_DIR"))
    certs_dir = Path(cfg.get("FS_CERTS_DIR"))
    fs.ensure_dir(secrets_dir)
    fs.ensure_dir(certs_dir)

    init_json = secrets_dir / "vault_init.json"

    vault_http_port = int(cfg.get("VAULT_HTTP_PORT"))
    base = f"http://127.0.0.1:{vault_http_port}"

    _wait_http_ready(base)

    if fs.exists(init_json):
        init_data = fs.read_json(init_json)
    else:
        init_data = _http_put_json(
            f"{base}/v1/sys/init",
            {"secret_shares": 1, "secret_threshold": 1},
            timeout_s=10.0,
            ok=(200,),
        )
        fs.write_json_atomic(init_json, init_data)

    root_token = str(init_data.get("root_token", "")).strip()
    unseal_key = str((init_data.get("keys") or [""])[0]).strip()
    if not root_token or not unseal_key:
        raise RuntimeError("vault_init_data_incomplete")

    hdr = _vault_headers(root_token)

    health = _http_get(f"{base}/v1/sys/health", timeout_s=2.0)
    if health.status_code in (472, 503):
        _http_put_json(f"{base}/v1/sys/unseal", {"key": unseal_key}, timeout_s=10.0, ok=(200,))
        health2 = _http_get(f"{base}/v1/sys/health", timeout_s=2.0)
        if health2.status_code == 503 and '"sealed":true' in (health2.text or "").replace(" ", "").lower():
            raise RuntimeError("vault_unseal_failed")

    try:
        _http_post_json(f"{base}/v1/sys/mounts/pki", {"type": "pki"}, headers=hdr, timeout_s=10.0, ok=(200, 204))
    except Exception:
        pass

    try:
        _http_post_json(
            f"{base}/v1/sys/mounts/pki/tune",
            {"max_lease_ttl": "87600h"},
            headers=hdr,
            timeout_s=10.0,
            ok=(200, 204),
        )
    except Exception:
        pass

    ca_file = certs_dir / "ca.crt"
    if not fs.exists(ca_file):
        try:
            _http_post_json(
                f"{base}/v1/pki/root/generate/internal",
                {"common_name": "terminal-ca", "ttl": "87600h"},
                headers=hdr,
                timeout_s=15.0,
                ok=(200,),
            )
        except Exception:
            pass

    ca_pem = _read_ca_pem(base)
    fs.write_text_atomic(ca_file, ca_pem)

    domain_root = str(cfg.get("GLOBAL_DOMAIN_ROOT"))
    _http_post_json(
        f"{base}/v1/pki/roles/terminal",
        {
            "allowed_domains": domain_root,
            "allow_subdomains": True,
            "allow_localhost": True,
            "allow_bare_domains": True,
            "allow_any_name": True,
            "enforce_hostnames": False,
            "max_ttl": "24h",
        },
        headers=hdr,
        timeout_s=10.0,
        ok=(200, 204),
    )

    def _issue_leaf(name: str) -> None:
        alt_names = f"{name},{name}.{domain_root}"
        issued = _http_post_json(
            f"{base}/v1/pki/issue/terminal",
            {"common_name": name, "alt_names": alt_names, "ttl": "24h"},
            headers=hdr,
            timeout_s=15.0,
            ok=(200,),
        )
        data = issued.get("data") or {}
        cert = str(data.get("certificate", "")).strip()
        key = str(data.get("private_key", "")).strip()
        if not cert or not key:
            raise RuntimeError(f"vault_issue_incomplete:{name}")

        crt = certs_dir / f"{name}.crt"
        k = certs_dir / f"{name}.key"
        pem = certs_dir / f"{name}.pem"

        fs.write_text_atomic(crt, cert + "\n")
        fs.write_text_atomic(k, key + "\n")
        _write_pem_bundle(fs, cert_path=crt, key_path=k, out_path=pem)

    for leaf in ("vault", "consul", "traefik"):
        _issue_leaf(leaf)

    required = [
        certs_dir / "ca.crt",
        certs_dir / "vault.pem",
        certs_dir / "consul.pem",
        certs_dir / "traefik.pem",
    ]
    for p in required:
        if not fs.exists(p) or not fs.read_text(p).strip():
            raise RuntimeError(f"missing_required_artifact:{p.name}")
