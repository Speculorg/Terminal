from __future__ import annotations

from pathlib import Path
from typing import Optional

from core._interfaces import IConfigs, IFS, ILogger, IMarkers


def _read_token(cfg: IConfigs, fs: IFS) -> str:
    # preferred: cfg.model.context.consul_token (filled from CONSUL_HTTP_TOKEN_FILE by Configs)
    try:
        model = getattr(cfg, "model", None)
        if model and getattr(model, "context", None) and getattr(model.context, "consul_token", None):
            v = str(model.context.consul_token).strip()
            if v:
                return v
    except Exception:
        pass

    # fallback: read from CONSUL_HTTP_TOKEN_FILE directly
    token_file = str(cfg.get("CONSUL_HTTP_TOKEN_FILE", "") or "").strip()
    if token_file:
        p = Path(token_file)
        if p.exists():
            v = fs.read_text(p).strip()
            if v:
                return v

    # last resort
    v = str(cfg.get("CONSUL_HTTP_TOKEN", "") or "").strip()
    return v


def traefik_bootstrap(*, cfg: IConfigs, fs: IFS, markers: IMarkers, log: Optional[ILogger] = None) -> None:
    """
    TERM-1 bootstrap для Traefik (идемпотентно):
    - генерирует /config/traefik_https.generated.yml с providers.consulCatalog,
      включая token + mTLS к Consul.
    """
    _ = markers  # выставляет BootstrapPolicy

    token = _read_token(cfg, fs)
    if not token:
        raise RuntimeError("traefik_bootstrap_missing_consul_token")

    consul_host = str(cfg.get("CONSUL_HOST", "consul"))
    consul_https_port = int(cfg.get("CONSUL_HTTPS_PORT", 8501) or 8501)

    certs_dir = Path(str(cfg.get("FS_CERTS_DIR", "/fs/terminal/certs")))
    ca_file = certs_dir / "ca.crt"
    cert_file = certs_dir / "traefik.crt"
    key_file = certs_dir / "traefik.key"

    out = Path("/config/traefik_https.generated.yml")

    if log:
        log.info("traefik_bootstrap:start", fields={"out": str(out), "consul": f"https://{consul_host}:{consul_https_port}"})

    cfg_text = f"""log:
  level: INFO

accessLog: {{}}

api:
  dashboard: true

entryPoints:
  websecure:
    address: ":8443"
    http:
      tls:
        options: mtls@file

providers:
  file:
    directory: /config
    watch: true

  consulCatalog:
    exposedByDefault: false
    defaultRule: "Host(`{{{{ .Name }}}}.terminal.speculorg.localhost`)"
    endpoint:
      address: "{consul_host}:{consul_https_port}"
      scheme: "https"
      token: "{token}"
      tls:
        ca: "{ca_file}"
        cert: "{cert_file}"
        key: "{key_file}"
"""

    fs.write_text_atomic(out, cfg_text)

    if log:
        log.info("traefik_bootstrap:written", fields={"bytes": len(cfg_text), "file": str(out)})

    # contract check
    if not fs.exists(out) or not fs.read_text(out).strip():
        raise RuntimeError("traefik_bootstrap_write_failed")
