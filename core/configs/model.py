from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class GlobalSection(BaseModel):
    domain_root: str = Field(default="terminal.local")


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
    http_port: int = Field(default=8200)
    pki_root_path: str = Field(default="pki-root")
    pki_role: str = Field(default="terminal-leaf")


class LoggingSection(BaseModel):
    level: str = Field(default="INFO")


class FSSection(BaseModel):
    markers_dir: str = Field(default="/fs/terminal/markers")
    secrets_dir: str = Field(default="/fs/terminal/secrets")
    certs_dir: str = Field(default="/fs/terminal/certs")
    tmp_dir: str = Field(default="/fs/terminal/tmp")


class TLSSection(BaseModel):
    watch_poll_interval_ms: int = Field(default=500)

    # rotate (TERM-1): ALWAYS ON, per-service
    rotate_check_interval_sec: int = Field(default=30)
    rotate_after_sec: int = Field(default=300)
    rotate_ttl: str = Field(default="10m")
    rotate_vault_addr: str = Field(default="https://vault:8200")
    rotate_vault_token_file: str = Field(default="/fs/terminal/secrets/vault_root_token.json")


class FSMSection(BaseModel):
    state_bootstrapping_timeout_ms: int = Field(default=5000)
    state_initializing_timeout_ms: int = Field(default=5000)
    state_securing_timeout_ms: int = Field(default=10000)
    state_registering_timeout_ms: int = Field(default=5000)
    state_running_tick_timeout_ms: int = Field(default=1000)


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
    logging: LoggingSection = Field(default_factory=LoggingSection)
    fs: FSSection = Field(default_factory=FSSection)
    tls: TLSSection = Field(default_factory=TLSSection)
    fsm: FSMSection = Field(default_factory=FSMSection)
    registrar: RegistrarSection = Field(default_factory=RegistrarSection)

    config_hash: str = Field(default="")