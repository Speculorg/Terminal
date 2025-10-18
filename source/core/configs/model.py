from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass(frozen=True)
class GlobalSection:
    domain_root: str = "localdomain"
    version: str = "0.0.0"

@dataclass(frozen=True)
class ContextSection:
    name: str = "default-name-service"
    port: int = 0
    tags: List[str] = field(default_factory=list)
    consul_token: Optional[str] = None

@dataclass(frozen=True)
class ConsulSection:
    host: str = "consul"
    http_port: int = 8500
    https_port: int = 8501
    scheme: str = "http"

@dataclass(frozen=True)
class VaultSection:
    host: str = "vault"
    http_port: int = 8200
    https_port: int = 8201
    scheme: str = "http"

@dataclass(frozen=True)
class TraefikSection:
    host: str = "traefik"
    https_port: int = 8443

@dataclass(frozen=True)
class LoggingSection:
    level: str = "INFO"

@dataclass(frozen=True)
class MetricsSection:
    path: str = "/metrics"
    port: int = 9090

@dataclass(frozen=True)
class FSSection:
    root_dir: str = "/app"
    markers_dir: str = "/app/fs/markers"
    secrets_dir: str = "/app/fs/secrets"
    certs_dir: str = "/app/fs/certs"

@dataclass(frozen=True)
class TLSSection:
    cert_name: str = "traefik"
    cert_path: str = "/app/fs/certs/traefik.crt"
    key_path: str = "/app/fs/certs/traefik.key"
    chain_path: str = "/app/fs/certs/traefik.fullchain"
    ca_path: str = "/app/fs/certs/ca.crt"
    certs_rotate_hours: int = 24

@dataclass(frozen=True)
class KVSection:
    request_timeout_ms: int = 2000

@dataclass(frozen=True)
class FSMSection:
    state_bootstrapping_timeout_ms: int = 15000
    state_initializing_timeout_ms: int = 30000
    state_securing_timeout_ms: int = 30000
    state_tls_transition_timeout_ms: int = 30000
    state_registering_timeout_ms: int = 15000

@dataclass(frozen=True)
class RegistrarSection:
    enabled: bool = True

@dataclass(frozen=True)
class ConfigModel:
    global_: GlobalSection = GlobalSection()
    context: ContextSection = ContextSection()
    consul: ConsulSection = ConsulSection()
    vault: VaultSection = VaultSection()
    traefik: TraefikSection = TraefikSection()
    logging: LoggingSection = LoggingSection()
    metrics: MetricsSection = MetricsSection()
    fs: FSSection = FSSection()
    tls: TLSSection = TLSSection()
    kv: KVSection = KVSection()
    fsm: FSMSection = FSMSection()
    registrar: RegistrarSection = RegistrarSection()
