"""
Unified settings loader for Speculorg.Terminal.
Groups: Domain, Consul, Vault, Traefik, Tls, Pki, Observability,
ServiceDefaults, Database, Keycloak, RabbitMQ.
"""

from dataclasses import dataclass, asdict
from typing import Any, Optional
import os
import json
import hashlib


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Domain:
    """Domain configuration."""
    root: str
    zone: Optional[str] = None
    wildcard: Optional[str] = None


@dataclass
class Consul:
    """Consul service settings."""
    service_name: str
    http_addr: str
    http_port: int
    https_addr: str
    https_port: int
    tls_enabled: bool


@dataclass
class Vault:
    """Vault settings."""
    service_name: str
    http_addr: str
    http_port: int
    https_addr: str
    https_port: int
    tls_enabled: bool
    pki_root_path: str
    pki_int_path: str
    pki_role_name: str
    cert_rotate_hours: int


@dataclass
class Traefik:
    """Traefik reverse proxy settings."""
    service_name: str
    http_port: int
    https_port: int
    tls_enabled: bool


@dataclass
class Tls:
    """Shared TLS options."""
    enabled: bool
    certs_dir: str


@dataclass
class Pki:
    """Public Key Infrastructure defaults."""
    leaf_ttl_hours: int
    san_list: list[str]


@dataclass
class Observability:
    """Metrics and dashboards."""
    prometheus_port: int
    grafana_port: int
    scrape_interval: str


@dataclass
class ServiceDefaults:
    """Base defaults for services."""
    health_dir: str
    init_timeout_s: int
    retry_interval_s: int
    backoff_factor: float
    max_retry_interval_s: int


@dataclass
class Database:
    """Database public settings."""
    service_name: str
    http_port: int


@dataclass
class Keycloak:
    """Keycloak public settings."""
    service_name: str
    http_port: int


@dataclass
class RabbitMQ:
    """RabbitMQ public settings."""
    service_name: str
    http_port: int


@dataclass
class Settings:
    domain: Domain
    consul: Consul
    vault: Vault
    traefik: Traefik
    tls: Tls
    pki: Pki
    observability: Observability
    service: ServiceDefaults
    database: Database
    keycloak: Keycloak
    rabbitmq: RabbitMQ


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: Optional[str], default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _parse_float(value: Optional[str], default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except ValueError:
        return default


def _parse_list(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def load_env_value(name: str, file_name: str) -> Optional[str]:
    """Load a value from environment variable or from file path variable."""
    val = os.getenv(name)
    if val is not None:
        return val
    path = os.getenv(file_name)
    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = f.read().strip()
                return data or None
        except OSError:
            return None
    return None


# ---------------------------------------------------------------------------
# Loading and hashing
# ---------------------------------------------------------------------------

def load_settings() -> Settings:
    env = os.environ

    domain = Domain(
        root=env.get("DOMAIN_ROOT", ""),
        zone=env.get("DOMAIN_ZONE"),
        wildcard=env.get("DOMAIN_WILDCARD"),
    )

    consul = Consul(
        service_name=env.get("CONSUL_SERVICE_NAME", ""),
        http_addr=env.get("CONSUL_HTTP_ADDR", ""),
        http_port=_parse_int(env.get("CONSUL_HTTP_PORT")),
        https_addr=env.get("CONSUL_HTTPS_ADDR", ""),
        https_port=_parse_int(env.get("CONSUL_HTTPS_PORT")),
        tls_enabled=_parse_bool(env.get("CONSUL_TLS_ENABLED")),
    )

    vault = Vault(
        service_name=env.get("VAULT_SERVICE_NAME", ""),
        http_addr=env.get("VAULT_HTTP_ADDR", ""),
        http_port=_parse_int(env.get("VAULT_HTTP_PORT")),
        https_addr=env.get("VAULT_HTTPS_ADDR", ""),
        https_port=_parse_int(env.get("VAULT_HTTPS_PORT")),
        tls_enabled=_parse_bool(env.get("VAULT_TLS_ENABLED")),
        pki_root_path=env.get("VAULT_PKI_ROOT_PATH", ""),
        pki_int_path=env.get("VAULT_PKI_INT_PATH", ""),
        pki_role_name=env.get("VAULT_PKI_ROLE_NAME", ""),
        cert_rotate_hours=_parse_int(env.get("VAULT_CERT_ROTATE_HOURS")),
    )

    traefik = Traefik(
        service_name=env.get("TRAEFIK_SERVICE_NAME", ""),
        http_port=_parse_int(env.get("TRAEFIK_HTTP_PORT")),
        https_port=_parse_int(env.get("TRAEFIK_HTTPS_PORT")),
        tls_enabled=_parse_bool(env.get("TRAEFIK_TLS_ENABLED")),
    )

    tls = Tls(
        enabled=_parse_bool(env.get("TLS_ENABLED")),
        certs_dir=env.get("TLS_CERTS_DIR", ""),
    )

    pki = Pki(
        leaf_ttl_hours=_parse_int(env.get("PKI_LEAF_TTL_HOURS")),
        san_list=_parse_list(env.get("PKI_SAN_LIST")),
    )

    observability = Observability(
        prometheus_port=_parse_int(env.get("OBS_PROMETHEUS_PORT")),
        grafana_port=_parse_int(env.get("OBS_GRAFANA_PORT")),
        scrape_interval=env.get("OBS_SCRAPE_INTERVAL", ""),
    )

    service = ServiceDefaults(
        health_dir=env.get("SERVICE_HEALTH_DIR", ""),
        init_timeout_s=_parse_int(env.get("SERVICE_INIT_TIMEOUT_S")),
        retry_interval_s=_parse_int(env.get("SERVICE_RETRY_INTERVAL_S")),
        backoff_factor=_parse_float(env.get("SERVICE_BACKOFF_FACTOR")),
        max_retry_interval_s=_parse_int(env.get("SERVICE_MAX_RETRY_INTERVAL_S")),
    )

    database = Database(
        service_name=env.get("DB_SERVICE_NAME", ""),
        http_port=_parse_int(env.get("DB_HTTP_PORT")),
    )

    keycloak = Keycloak(
        service_name=env.get("KC_SERVICE_NAME", ""),
        http_port=_parse_int(env.get("KC_HTTP_PORT")),
    )

    rabbitmq = RabbitMQ(
        service_name=env.get("MQ_SERVICE_NAME", ""),
        http_port=_parse_int(env.get("MQ_HTTP_PORT")),
    )

    return Settings(
        domain=domain,
        consul=consul,
        vault=vault,
        traefik=traefik,
        tls=tls,
        pki=pki,
        observability=observability,
        service=service,
        database=database,
        keycloak=keycloak,
        rabbitmq=rabbitmq,
    )


def _sorted(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _sorted(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [_sorted(v) for v in obj]
    return obj


def config_hash(settings: Settings) -> str:
    """Calculate SHA-256 hash from sorted settings dictionary."""
    data = asdict(settings)
    canonical = _sorted(data)
    dumped = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


SETTINGS = load_settings()
CONFIG_HASH = config_hash(SETTINGS)
