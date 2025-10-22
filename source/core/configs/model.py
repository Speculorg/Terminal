from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass(frozen=True)
class GlobalSection:
    domain_root: str = "terminal.local"
    version: str = "0.0.0-dev"

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

@dataclass(frozen=True)
class VaultSection:
    host: str = "vault"
    http_port: int = 8200
    https_port: int = 8200  # обычно тот же 8200, оставлен для единообразия
    pki_root_path: str = "pki-root"
    pki_int_path: str = "pki-int"
    pki_role: str = "terminal-leaf"

@dataclass(frozen=True)
class TraefikSection:
    host: str = "traefik"
    http_port: int = 8080
    https_port: int = 8443

@dataclass(frozen=True)
class LoggingSection:
    level: str = "INFO"
    correlation_id_header: str = "X-Request-ID"
    generate_correlation_if_missing: bool = True
    correlation_id_len_max: int = 64

@dataclass(frozen=True)
class MetricsSection:
    host: str = "0.0.0.0"
    path: str = "/metrics"
    port: int = 8000

@dataclass(frozen=True)
class FSSection:
    certs_dir: str = "/certs"
    secrets_dir: str = "/secrets"

@dataclass(frozen=True)
class TLSSection:
    certs_rotate_hours: int = 168
    reloader_strategy: str = "SSL_CTX"
    watch_debounce_ms: int = 300
    watch_poll_interval_ms: int = 500

@dataclass(frozen=True)
class KVSection:
    cas_backoff_factor: int = 2
    cas_max_retries: int = 5
    request_timeout_ms: int = 5000

@dataclass(frozen=True)
class FSMSection:
    state_bootstrapping_timeout_ms: int = 5000
    state_initializing_timeout_ms: int = 15000
    state_securing_timeout_ms: int = 10000
    state_tls_transition_timeout_ms: int = 5000
    state_registering_timeout_ms: int = 5000
    state_running_tick_timeout_ms: int = 1000
    state_publish_min_interval_ms: int = 5000
    degraded_recovery_window_ms: int = 60000
    degraded_transition_window_ms: int = 30000
    degraded_min_duration_ms: int = 5000

@dataclass(frozen=True)
class RegistrarSection:
    ttl_sec: int = 15
    heartbeat_period_sec: int = 7
    deregister_critical_service_after_sec: int = 45
    reregistration_cooldown_sec: int = 15
    max_rereg_attempts_per_window: int = 5

@dataclass(frozen=True)
class Model:
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
