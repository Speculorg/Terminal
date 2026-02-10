from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

from core._interfaces import IConfigs, IFS, ILogger, IMarkers


def vault_bootstrap(*, cfg: IConfigs, fs: IFS, markers: IMarkers, log: Optional[ILogger] = None) -> None:
    """
    Vault FIRST bootstrap (HTTP window), идемпотентно:
    - init/unseal (если нужно)
    - PKI mount + root CA
    - роль для leaf
    - выпуск leaf сертификатов для {consul, vault, traefik}
    - запись CA + leaf в FS_CERTS_DIR

    Маркеры выставляет BootstrapPolicy после успешного завершения.
    """
    _ = markers  # маркеры выставляет BootstrapPolicy

    http_port = str(cfg.get("VAULT_HTTP_PORT", "8200"))
    base_url = f"http://127.0.0.1:{http_port}"

    secrets_dir = Path(str(cfg.get("FS_SECRETS_DIR", "/fs/terminal/secrets")))
    certs_dir = Path(str(cfg.get("FS_CERTS_DIR", "/fs/terminal/certs")))

    pki_path = str(cfg.get("VAULT_PKI_ROOT_PATH", "pki")).strip().strip("/")
    pki_role = str(cfg.get("VAULT_PKI_ROLE", "terminal-leaf")).strip()
    domain_root = str(cfg.get("GLOBAL_DOMAIN_ROOT", "terminal.local")).strip().strip(".")

    # Требование Q5:
    # {consul, vault, traefik, localhost, 127.0.0.1} + {<name>.<domain_root>}
    base_dns_sans = ["consul", "vault", "traefik", "localhost"]
    base_ip_sans = ["127.0.0.1"]

    root_token_path = secrets_dir / "vault_root_token.json"
    unseal_keys_path = secrets_dir / "vault_unseal_keys.json"

    ca_crt_path = certs_dir / "ca.crt"
    leaf_targets = ["consul", "vault", "traefik"]

    fs.ensure_dir(str(secrets_dir))
    fs.ensure_dir(str(certs_dir))

    _log(log, "vault_bootstrap:start", fields={"base_url": base_url, "pki_path": pki_path, "pki_role": pki_role, "domain_root": domain_root})

    sess = requests.Session()
    _wait_vault_reachable(sess=sess, base_url=base_url, log=log, timeout_s=90.0)

    initialized = _vault_sys_init_get(sess=sess, base_url=base_url)
    if not initialized:
        _log(log, "vault_bootstrap:init:begin")
        init_resp = _vault_sys_init_post(sess=sess, base_url=base_url, shares=1, threshold=1)
        root_token = init_resp["root_token"]
        keys = init_resp["keys"]
        if not isinstance(keys, list) or not keys or not isinstance(keys[0], str):
            raise RuntimeError("vault_bootstrap:init:invalid_unseal_keys")

        fs.write_json_atomic(str(root_token_path), {"root_token": root_token}, mode=0o600)
        fs.write_json_atomic(str(unseal_keys_path), {"keys": keys, "threshold": 1}, mode=0o600)
        _log(log, "vault_bootstrap:init:done", fields={"root_token_path": str(root_token_path), "unseal_keys_path": str(unseal_keys_path)})
    else:
        if not root_token_path.exists():
            raise RuntimeError(f"vault_bootstrap:error:initialized_but_root_token_missing:{root_token_path}")
        if not unseal_keys_path.exists():
            raise RuntimeError(f"vault_bootstrap:error:initialized_but_unseal_keys_missing:{unseal_keys_path}")
        _log(log, "vault_bootstrap:init:skip", fields={"reason": "already_initialized", "root_token_path": str(root_token_path)})

    root_token = _read_root_token(path=root_token_path)
    unseal_key = _read_first_unseal_key(path=unseal_keys_path)

    seal = _vault_sys_seal_status(sess=sess, base_url=base_url)
    if seal.get("sealed", True):
        _log(log, "vault_bootstrap:unseal:begin")
        _vault_sys_unseal(sess=sess, base_url=base_url, key=unseal_key)
        seal2 = _vault_sys_seal_status(sess=sess, base_url=base_url)
        if seal2.get("sealed", True):
            raise RuntimeError("vault_bootstrap:unseal:failed")
        _log(log, "vault_bootstrap:unseal:done")
    else:
        _log(log, "vault_bootstrap:unseal:skip", fields={"reason": "already_unsealed"})

    hdr = {"X-Vault-Token": root_token}

    _ensure_pki_mount(sess=sess, base_url=base_url, hdr=hdr, pki_path=pki_path)

    ca_pem = _ensure_root_ca(sess=sess, base_url=base_url, hdr=hdr, pki_path=pki_path, domain_root=domain_root)
    fs.write_text_atomic(str(ca_crt_path), ca_pem.strip() + "\n", mode=0o644)
    _log(log, "vault_bootstrap:pki:ca:persisted", fields={"ca_crt_path": str(ca_crt_path)})

    # КРИТИЧНОЕ ИСПРАВЛЕНИЕ:
    # allow_any_name=true, иначе Vault отвергает SAN вида "consul"/"vault"/"traefik"
    _ensure_leaf_role(
        sess=sess,
        base_url=base_url,
        hdr=hdr,
        pki_path=pki_path,
        role=pki_role,
        domain_root=domain_root,
        allow_any_name=True,
    )

    for svc in leaf_targets:
        crt_path = certs_dir / f"{svc}.crt"
        key_path = certs_dir / f"{svc}.key"
        pem_path = certs_dir / f"{svc}.pem"

        if crt_path.exists() and key_path.exists():
            _log(log, "vault_bootstrap:pki:issue:skip", fields={"service": svc, "reason": "cert_and_key_exist"})
            continue

        dns_sans = _unique_list(base_dns_sans + [f"{svc}.{domain_root}"])
        ip_sans = _unique_list(base_ip_sans)
        common_name = f"{svc}.{domain_root}"

        _log(log, "vault_bootstrap:pki:issue:begin", fields={"service": svc, "common_name": common_name, "alt_names": dns_sans, "ip_sans": ip_sans})

        issued = _pki_issue(
            sess=sess,
            base_url=base_url,
            hdr=hdr,
            pki_path=pki_path,
            role=pki_role,
            common_name=common_name,
            alt_names=dns_sans,
            ip_sans=ip_sans,
            ttl="24h",
        )

        cert_pem = str(issued["certificate"]).strip() + "\n"
        key_pem = str(issued["private_key"]).strip() + "\n"

        fs.write_text_atomic(str(crt_path), cert_pem, mode=0o644)
        fs.write_text_atomic(str(key_path), key_pem, mode=0o600)
        fs.write_text_atomic(str(pem_path), cert_pem + key_pem, mode=0o600)

        _log(log, "vault_bootstrap:pki:issue:done", fields={"service": svc, "crt": str(crt_path), "key": str(key_path), "pem": str(pem_path)})

    _log(log, "vault_bootstrap:done", fields={"leaf_targets": leaf_targets})


def _log(log: Optional[ILogger], msg: str, *, fields: Optional[Dict[str, Any]] = None) -> None:
    if log is None:
        return
    log.info(msg, fields=fields)


def _wait_vault_reachable(*, sess: requests.Session, base_url: str, log: Optional[ILogger], timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    last_err: Optional[str] = None

    while time.time() < deadline:
        try:
            r = sess.get(f"{base_url}/v1/sys/health", timeout=(1.5, 3.0))
            if r.status_code in (200, 429, 472, 473, 501, 503):
                _log(log, "vault_bootstrap:wait:ok", fields={"status_code": r.status_code})
                return
            last_err = f"unexpected_status:{r.status_code}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}:{e}"

        _log(log, "vault_bootstrap:wait:retry", fields={"base_url": base_url, "last_err": last_err})
        time.sleep(0.5)

    raise RuntimeError(f"vault_bootstrap:wait:timeout:{last_err}")


def _vault_sys_init_get(*, sess: requests.Session, base_url: str) -> bool:
    r = sess.get(f"{base_url}/v1/sys/init", timeout=(2.0, 5.0))
    if r.status_code != 200:
        raise RuntimeError(f"vault_bootstrap:sys:init:get_failed:{r.status_code}:{r.text}")
    data = r.json()
    return bool(data.get("initialized", False))


def _vault_sys_init_post(*, sess: requests.Session, base_url: str, shares: int, threshold: int) -> Dict[str, Any]:
    r = sess.post(
        f"{base_url}/v1/sys/init",
        json={"secret_shares": int(shares), "secret_threshold": int(threshold)},
        timeout=(5.0, 15.0),
    )
    if r.status_code not in (200, 204):
        raise RuntimeError(f"vault_bootstrap:sys:init:post_failed:{r.status_code}:{r.text}")
    return dict(r.json() or {})


def _vault_sys_seal_status(*, sess: requests.Session, base_url: str) -> Dict[str, Any]:
    r = sess.get(f"{base_url}/v1/sys/seal-status", timeout=(2.0, 5.0))
    if r.status_code != 200:
        raise RuntimeError(f"vault_bootstrap:sys:seal_status_failed:{r.status_code}:{r.text}")
    return dict(r.json() or {})


def _vault_sys_unseal(*, sess: requests.Session, base_url: str, key: str) -> None:
    r = sess.post(f"{base_url}/v1/sys/unseal", json={"key": key}, timeout=(5.0, 15.0))
    if r.status_code not in (200, 204):
        raise RuntimeError(f"vault_bootstrap:sys:unseal_failed:{r.status_code}:{r.text}")


def _ensure_pki_mount(*, sess: requests.Session, base_url: str, hdr: Dict[str, str], pki_path: str) -> None:
    r = sess.get(f"{base_url}/v1/sys/mounts", headers=hdr, timeout=(3.0, 10.0))
    if r.status_code != 200:
        raise RuntimeError(f"vault_bootstrap:sys:mounts_failed:{r.status_code}:{r.text}")
    mounts = dict(r.json() or {})
    if f"{pki_path}/" in mounts:
        return

    r2 = sess.post(
        f"{base_url}/v1/sys/mounts/{pki_path}",
        headers=hdr,
        json={"type": "pki"},
        timeout=(5.0, 15.0),
    )
    if r2.status_code not in (200, 204):
        raise RuntimeError(f"vault_bootstrap:pki:mount_failed:{r2.status_code}:{r2.text}")


def _ensure_root_ca(*, sess: requests.Session, base_url: str, hdr: Dict[str, str], pki_path: str, domain_root: str) -> str:
    r = sess.get(f"{base_url}/v1/{pki_path}/ca/pem", headers=hdr, timeout=(3.0, 10.0))
    if r.status_code == 200 and (r.text or "").strip().startswith("-----BEGIN CERTIFICATE-----"):
        return r.text

    r2 = sess.post(
        f"{base_url}/v1/{pki_path}/root/generate/internal",
        headers=hdr,
        json={"common_name": domain_root, "ttl": "8760h"},
        timeout=(5.0, 20.0),
    )
    if r2.status_code not in (200, 204):
        raise RuntimeError(f"vault_bootstrap:pki:root_generate_failed:{r2.status_code}:{r2.text}")

    data = dict(r2.json() or {})
    cert = str(data.get("data", {}).get("certificate", "") or "").strip()
    if cert:
        return cert

    r3 = sess.get(f"{base_url}/v1/{pki_path}/ca/pem", headers=hdr, timeout=(3.0, 10.0))
    if r3.status_code == 200:
        return r3.text
    raise RuntimeError("vault_bootstrap:pki:ca_missing_after_generate")


def _ensure_leaf_role(
    *,
    sess: requests.Session,
    base_url: str,
    hdr: Dict[str, str],
    pki_path: str,
    role: str,
    domain_root: str,
    allow_any_name: bool,
) -> None:
    payload: Dict[str, Any] = {
        "allowed_domains": domain_root,
        "allow_subdomains": True,
        "allow_bare_domains": True,
        "allow_localhost": True,
        "allow_ip_sans": True,
        "max_ttl": "24h",
    }
    if allow_any_name:
        payload["allow_any_name"] = True

    r = sess.post(
        f"{base_url}/v1/{pki_path}/roles/{role}",
        headers=hdr,
        json=payload,
        timeout=(5.0, 15.0),
    )
    if r.status_code not in (200, 204):
        raise RuntimeError(f"vault_bootstrap:pki:role_write_failed:{r.status_code}:{r.text}")


def _pki_issue(
    *,
    sess: requests.Session,
    base_url: str,
    hdr: Dict[str, str],
    pki_path: str,
    role: str,
    common_name: str,
    alt_names: Iterable[str],
    ip_sans: Iterable[str],
    ttl: str,
) -> Dict[str, Any]:
    r = sess.post(
        f"{base_url}/v1/{pki_path}/issue/{role}",
        headers=hdr,
        json={
            "common_name": common_name,
            "alt_names": ",".join(list(alt_names)),
            "ip_sans": ",".join(list(ip_sans)),
            "ttl": ttl,
        },
        timeout=(5.0, 20.0),
    )
    if r.status_code not in (200, 204):
        # важно: текст Vault нужен для диагностики (обычно там "name not allowed by this role")
        raise RuntimeError(f"vault_bootstrap:pki:issue_failed:{r.status_code}:{(r.text or '')[:256]}")
    data = dict(r.json() or {})
    return dict(data.get("data", {}) or {})


def _unique_list(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for x in items:
        v = str(x).strip()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _read_root_token(*, path: Path) -> str:
    d = _read_json(path)
    token = str(d.get("root_token", "") or "").strip()
    if not token:
        raise RuntimeError(f"vault_bootstrap:root_token_empty:{path}")
    return token


def _read_first_unseal_key(*, path: Path) -> str:
    d = _read_json(path)
    keys = d.get("keys", [])
    if not isinstance(keys, list) or not keys:
        raise RuntimeError(f"vault_bootstrap:unseal_keys_empty:{path}")
    k0 = str(keys[0] or "").strip()
    if not k0:
        raise RuntimeError(f"vault_bootstrap:unseal_key_empty:{path}")
    return k0


def _read_json(path: Path) -> Dict[str, Any]:
    import json
    raw = path.read_text(encoding="utf-8")
    return dict(json.loads(raw or "{}") or {})
