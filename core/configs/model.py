from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class GlobalSection(BaseModel):
    domain_root: str = Field(default="terminal.local")


class ContextSection(BaseModel):
    # SERVICE_NAME/SERVICE_PORT/SERVICE_TAGS приходят из docker-compose environment.
    name: str = Field(default="default-name-service")
    port: int = Field(default=0)
    tags: List[str] = Field(default_factory=list)

    # Содержимое токена (прочитано из CONSUL_HTTP_TOKEN_FILE).
    # Важно: сам путь CONSUL_HTTP_TOKEN_FILE остаётся в raw env, а не в модели.
    consul_token: Optional[str] = Field(default=None)


class ConsulSection(BaseModel):
    host: str = Field(default="consul")
    http_port: int = Field(default=8500)
    https_port: int = Field(default=8501)


class VaultSection(BaseModel):
    # TERM-1: используется для HTTP bootstrap окна и для PKI путей/роли.
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
    # TERM-1: используется DaemonPolicy для polling TLS bundle.
    watch_poll_interval_ms: int = Field(default=500)


class FSMSection(BaseModel):
    # Дедлайны состояний (ms). 0 = без дедлайна.
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

    # детерминированный хэш ключевых секций (паспорт конфигурации)
    config_hash: str = Field(default="")