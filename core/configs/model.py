from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class GlobalSection(BaseModel):
    domain_root: str = Field(default="terminal.local")
    version: str = Field(default="0.0.0-dev")


class ContextSection(BaseModel):
    name: str = Field(default="default-name-service")
    port: int = Field(default=0)
    tags: List[str] = Field(default_factory=list)
    consul_token: Optional[str] = Field(default=None)


class ConsulSection(BaseModel):
    host: str = Field(default="consul")
    http_port: int = Field(default=8500)
    https_port: int = Field(default=8501)


class VaultSection(BaseModel):
    host: str = Field(default="vault")
    http_port: int = Field(default=8200)
    https_port: int = Field(default=8200)
    pki_root_path: str = Field(default="pki-root")
    pki_int_path: str = Field(default="pki-int")
    pki_role: str = Field(default="terminal-leaf")


class TraefikSection(BaseModel):
    host: str = Field(default="traefik")
    http_port: int = Field(default=8080)
    https_port: int = Field(default=8443)


class LoggingSection(BaseModel):
    level: str = Field(default="INFO")
    correlation_id_header: str = Field(default="X-Request-ID")
    generate_correlation_if_missing: bool = Field(default=True)
    correlation_id_len_max: int = Field(default=64)


class MetricsSection(BaseModel):
    host: str = Field(default="0.0.0.0")
    path: str = Field(default="/metrics")
    port: int = Field(default=8000)


class FSSection(BaseModel):
    markers_dir: str = Field(default="/fs/terminal/markers")
    secrets_dir: str = Field(default="/fs/terminal/secrets")
    certs_dir: str = Field(default="/fs/terminal/certs")
    tmp_dir: str = Field(default="/fs/terminal/tmp")


class TLSSection(BaseModel):
    certs_rotate_hours: int = Field(default=168)
    reloader_strategy: str = Field(default="NONE")
    watch_debounce_ms: int = Field(default=300)
    watch_poll_interval_ms: int = Field(default=500)


class KVSection(BaseModel):
    cas_backoff_factor: int = Field(default=2)
    cas_max_retries: int = Field(default=4)
    request_timeout_ms: int = Field(default=3000)


class FSMSection(BaseModel):
    # NOTE: будет миграция на deadline (`cfg.fsm.state_[state]_deadline_ms`) по плану TERM-1
    state_bootstrapping_timeout_ms: int = Field(default=5000)
    state_initializing_timeout_ms: int = Field(default=5000)
    state_securing_timeout_ms: int = Field(default=10000)
    state_tls_transition_timeout_ms: int = Field(default=5000)
    state_registering_timeout_ms: int = Field(default=5000)
    state_running_tick_timeout_ms: int = Field(default=1000)

    state_publish_min_interval_ms: int = Field(default=5000)

    degraded_recovery_window_ms: int = Field(default=60000)
    degraded_transition_window_ms: int = Field(default=30000)
    degraded_min_duration_ms: int = Field(default=5000)


class RegistrarSection(BaseModel):
    ttl_sec: int = Field(default=15)
    heartbeat_period_sec: int = Field(default=7)
    deregister_critical_service_after_sec: int = Field(default=45)
    reregistration_cooldown_sec: int = Field(default=15)
    max_rereg_attempts_per_window: int = Field(default=5)


class Model(BaseModel):
    global_: GlobalSection = Field(default_factory=GlobalSection)
    context: ContextSection = Field(default_factory=ContextSection)
    consul: ConsulSection = Field(default_factory=ConsulSection)
    vault: VaultSection = Field(default_factory=VaultSection)
    traefik: TraefikSection = Field(default_factory=TraefikSection)
    logging: LoggingSection = Field(default_factory=LoggingSection)
    metrics: MetricsSection = Field(default_factory=MetricsSection)
    fs: FSSection = Field(default_factory=FSSection)
    tls: TLSSection = Field(default_factory=TLSSection)
    kv: KVSection = Field(default_factory=KVSection)
    fsm: FSMSection = Field(default_factory=FSMSection)
    registrar: RegistrarSection = Field(default_factory=RegistrarSection)

    # детерминированный хэш ключевых секций (паспорт конфигурации)
    config_hash: str = Field(default="")
