from __future__ import annotations

from pathlib import Path
from typing import Optional

import requests

from core._interfaces import IConfigs, IFS, ILogger, IMarkers


def _http_get_text(url: str, *, timeout_ms: int = 2000) -> str:
    r = requests.get(url, timeout=max(0.2, timeout_ms / 1000.0))
    if r.status_code >= 300:
        raise RuntimeError(f"http_error:{r.status_code}:{(r.text or '')[:256]}")
    return r.text or ""


def _http_put_json(url: str, *, timeout_ms: int = 3000) -> dict:
    r = requests.put(url, timeout=max(0.2, timeout_ms / 1000.0))
    if r.status_code >= 300:
        raise RuntimeError(f"http_error:{r.status_code}:{(r.text or '')[:256]}")
    if not r.text:
        return {}
    try:
        return r.json()
    except Exception:
        return {}


def consul_bootstrap(*, cfg: IConfigs, fs: IFS, markers: IMarkers, log: Optional[ILogger] = None) -> None:
    """
    TERM-1 bootstrap для Consul (idempotent):

    - Consul работает в bootstrap-окно по HTTP на 127.0.0.1:8500 (см. consul_http.hcl)
    - если ACL bootstrap token уже сохранён — повтор не делает ничего
    - иначе выполняет /v1/acl/bootstrap и сохраняет результат в FS_SECRETS_DIR

    Маркеры:
    - consul_bootstrap.done
    - consul_tokens.done
    """
    if markers.has("consul_bootstrap.done") and markers.has("consul_tokens.done"):
        return

    secrets_dir = Path(str(cfg.get("FS_SECRETS_DIR", "/fs/terminal/secrets")))
    fs.ensure_dir(secrets_dir)

    token_path = secrets_dir / "consul_acl_bootstrap_token.json"
    if fs.exists(token_path):
        markers.set("consul_bootstrap.done")
        markers.set("consul_tokens.done")
        return

    port = int(cfg.get("CONSUL_HTTP_PORT", 8500) or 8500)
    base = f"http://127.0.0.1:{port}"

    # 1) дождаться агента
    _http_get_text(f"{base}/v1/status/leader", timeout_ms=2000)

    # 2) ACL bootstrap
    doc = _http_put_json(f"{base}/v1/acl/bootstrap", timeout_ms=3000)
    if not doc.get("SecretID"):
        raise RuntimeError("consul_acl_bootstrap_failed")

    fs.write_json_atomic(token_path, doc)

    markers.set("consul_bootstrap.done")
    markers.set("consul_tokens.done")

    if log is not None:
        try:
            log.event("consul.bootstrap.ok", fields={"token_file": str(token_path)})
        except Exception:
            pass
