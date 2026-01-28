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


def _wait_http_ready(base: str, *, timeout_s: float = 60.0, log: ILogger | None = None) -> None:
    t0 = time.time()
    while True:
        try:
            r = _http_get(f"{base}/v1/sys/health", timeout_s=2.0)
            if r.status_code in (200, 429, 472, 473, 501, 503) and (r.text or ""):
                if log is not None:
                    log.info("vault_bootstrap:http_ready", fields={"status": r.status_code})
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

    1) init + unseal (root token + unseal keys сохраняются на диск)
    2) PKI: enable pki, tune, generate root CA, role issue, leaf сертификаты:
       - vault, consul, traefik (PEM-bundle для upstream mTLS)
    3) Экспорт CA PEM в /fs/terminal/certs/ca.crt + bundles *.pem

    Маркеры здесь НЕ выставляются (это делает BootstrapPolicy ядра).
    """
    _ = markers  # маркеры управляются ядром

    def _log(msg: str, **fields) -> None:
        if log is None:
            return
        log.info(msg, fields=fields or None)

    secrets_dir = Path(str(cfg.get("FS_SECRETS_DIR", "/fs/terminal/secrets")))
    certs_dir = Path(str(cfg.get("FS_CERTS_DIR", "/fs/terminal/certs")))
    fs.ensure_dir(secrets_dir)
    fs.ensure_dir(certs_dir)

    root_token_file = secrets_dir / "root_vault_token.txt"
    unseal_keys_file = secrets_dir / "vault_unseal_keys.json"

    vault_http_port = int(cfg.get("VAULT_HTTP_PORT", 8200) or 8200)
    base = f"http://127.0.0.1:{vault_http_port}"
    _log("vault_bootstrap:start", base=base, secrets_dir=str(secrets_dir), certs_dir=str(certs_dir))

    _log("vault_bootstrap:wait_http_ready", url=f"{base}/v1/sys/health")
    _wait_http_ready(base, log=log)

    # --- init (idempotent) ---
    root_token = fs.read_text(root_token_file).strip() if fs.exists(root_token_file) else ""
    unseal_keys: list[str] = []
    if fs.exists(unseal_keys_file):
        data = fs.read_json(unseal_keys_file)
        unseal_keys = list(data.get("keys", []) or [])

    if not root_token or not unseal_keys:
        _log("vault_bootstrap:init:request")
        init = _http_put_json(
            f"{base}/v1/sys/init",
            {
                "secret_shares": 1,
                "secret_threshold": 1,
            },
            timeout_s=10.0,
            ok=(200,),
        )
        root_token = str(init.get("root_token", "")).strip()
        keys = init.get("keys", []) or []
        unseal_keys = [str(k).strip() for k in keys if str(k).strip()]
        if not root_token or not unseal_keys:
            raise RuntimeError("vault_init_missing_artifacts")

        fs.write_text_atomic(root_token_file, root_token + "\n")
        fs.write_json_atomic(unseal_keys_file, {"keys": unseal_keys})
        _log("vault_bootstrap:init:ok", root_token_file=str(root_token_file), unseal_keys_file=str(unseal_keys_file))

    # --- unseal (idempotent) ---
    hdr = _vault_headers(root_token)
    health = _http_get(f"{base}/v1/sys/health", timeout_s=2.0)
    sealed = False
    try:
        sealed = bool(health.json().get("sealed", False))
    except Exception:
        sealed = False

    if sealed:
        _log("vault_bootstrap:unseal:start")
        for k in unseal_keys[:1]:
            _http_put_json(f"{base}/v1/sys/unseal", {"key": k}, timeout_s=10.0, ok=(200,))
        _log("vault_bootstrap:unseal:ok")

    # --- PKI setup ---
    # enable pki (idempotent)
    st = _http_get(f"{base}/v1/sys/mounts/pki", headers=hdr, timeout_s=5.0).status_code
    if st == 404:
        _log("vault_bootstrap:pki:enable")
        _http_post_json(f"{base}/v1/sys/mounts/pki", {"type": "pki"}, headers=hdr, timeout_s=10.0, ok=(204,))
    else:
        _log("vault_bootstrap:pki:mount_exists", status=st)

    # tune
    _log("vault_bootstrap:pki:tune")
    _http_post_json(f"{base}/v1/sys/mounts/pki/tune", {"max_lease_ttl": "8760h"}, headers=hdr, timeout_s=10.0, ok=(204,))

    # root CA (generate once)
    ca_pem_path = certs_dir / "ca.crt"
    if not fs.exists(ca_pem_path) or not fs.read_text(ca_pem_path).strip():
        _log("vault_bootstrap:pki:generate_root")
        _http_put_json(
            f"{base}/v1/pki/root/generate/internal",
            {"common_name": "terminal.local", "ttl": "8760h"},
            headers=hdr,
            timeout_s=10.0,
            ok=(200,),
        )
        ca_pem = _read_ca_pem(base)
        fs.write_text_atomic(ca_pem_path, ca_pem)
        _log("vault_bootstrap:pki:root_ready", ca_file=str(ca_pem_path))
    else:
        _log("vault_bootstrap:pki:root_exists", ca_file=str(ca_pem_path))

    # role (issue)
    _log("vault_bootstrap:pki:role_upsert")
    _http_post_json(
        f"{base}/v1/pki/roles/terminal-leaf",
        {
            "allowed_domains": "terminal.local",
            "allow_subdomains": True,
            "max_ttl": "24h",
        },
        headers=hdr,
        timeout_s=10.0,
        ok=(204,),
    )

    # issue leaves for required services
    def _issue(name: str) -> tuple[str, str]:
        d = _http_post_json(
            f"{base}/v1/pki/issue/terminal-leaf",
            {"common_name": f"{name}.terminal.local", "ttl": "24h"},
            headers=hdr,
            timeout_s=10.0,
            ok=(200,),
        )
        cert = str(d.get("data", {}).get("certificate", "") or "")
        key = str(d.get("data", {}).get("private_key", "") or "")
        if not cert.strip() or not key.strip():
            raise RuntimeError(f"vault_issue_empty_leaf:{name}")
        return cert, key

    for svc in ("vault", "consul", "traefik"):
        crt = certs_dir / f"{svc}.crt"
        key = certs_dir / f"{svc}.key"
        pem = certs_dir / f"{svc}.pem"
        if fs.exists(crt) and fs.exists(key) and fs.read_text(crt).strip() and fs.read_text(key).strip():
            _log("vault_bootstrap:pki:leaf_exists", svc=svc)
        else:
            _log("vault_bootstrap:pki:issue_leaf", svc=svc)
            cert, priv = _issue(svc)
            fs.write_text_atomic(crt, cert.strip() + "\n")
            fs.write_text_atomic(key, priv.strip() + "\n")

        # bundle
        _write_pem_bundle(fs, cert_path=crt, key_path=key, out_path=pem)

    required = [
        certs_dir / "ca.crt",
        certs_dir / "vault.pem",
        certs_dir / "consul.pem",
        certs_dir / "traefik.pem",
    ]
    for p in required:
        if not fs.exists(p) or not fs.read_text(p).strip():
            raise RuntimeError(f"missing_required_artifact:{p.name}")

    _log("vault_bootstrap:ok", artifacts=[str(p) for p in required])
