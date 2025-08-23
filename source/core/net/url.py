# source\core\net\url.py


"""
Small URL helpers. Pure functions, no global state.
Keep this module settings-agnostic: pass all values explicitly.
"""

from __future__ import annotations
from typing import Mapping


def fqdn(name: str, domain_root: str) -> str:
    """Build FQDN like 'consul.terminal.speculorg.localhost'."""
    name = name.strip().strip(".")
    domain_root = domain_root.strip().strip(".")
    return f"{name}.{domain_root}" if name else domain_root


def normalize_path(path: str) -> str:
    """Ensure path starts with single '/', without trailing slash (except '/')."""
    p = "/" + path.lstrip("/")
    return p if p == "/" else p.rstrip("/")


def build_url(host: str, port_http: int, port_https: int, path: str = "", tls: bool = False) -> str:
    """
    Build http(s) URL for a service depending on TLS flag.
    Example:
        build_url("consul", 8500, 8501, "/v1/agent", tls=False)
    """
    scheme = "https" if tls else "http"
    port = int(port_https if tls else port_http)
    p = normalize_path(path) if path else ""
    return f"{scheme}://{host}:{port}{p}"


def build_host_url(
    name: str,
    domain_root: str,
    port_http: int,
    port_https: int,
    path: str = "",
    tls: bool = False,
) -> str:
    """Build URL using service name + domain_root."""
    return build_url(fqdn(name, domain_root), port_http, port_https, path, tls)


def add_query(url: str, params: Mapping[str, str] | None) -> str:
    """Append query string to URL (no encoding, keep simple)."""
    if not params:
        return url
    tail = "&".join(f"{k}={v}" for k, v in params.items())
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{tail}"
