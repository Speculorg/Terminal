"""
Speculorg.Terminal :: core.settings.settings

Назначение:
- Считать параметры окружения (settings.env), привести типы, задать дефолты.
- Построить производные значения (например, SAN-список для mTLS на базе DOMAIN_ROOT).
- Предоставить единый API:
    SETTINGS     - неизменяемая (по договорённости) структура настроек.
    CONFIG_HASH  - детерминированный SHA-256 по значимым (несекретным) полям.

Принципы:
- Только стандартная библиотека (Python 3.12).
- Никаких секретов: пароли/токены/DSN здесь не читаются.
- Код приложения использует ТОЛЬКО SETTINGS (никаких os.environ прямо).
- Константы исполнения (например, PYTHONUNBUFFERED/PYTHONPATH) - в compose/Dockerfile.

Слои:
- Domain, Paths, Timeouts, Consul, Vault, Traefik, Database, Observability, Policy.
- Context - паспорт текущего экземпляра сервиса (name/port/tags/health_file).
  Context используется в коде, но исключается из CONFIG_HASH (кластерный дрейф не должен
  зависеть от конкретного экземпляра).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from typing import Any, List, Tuple


# ----------------------------
# Helpers: env parsing & utils
# ----------------------------

def _env_str(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None or v.strip() == "" else v.strip()


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    try:
        return int(v.strip())
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    try:
        return float(v.strip())
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    s = v.strip().lower()
    if s == "":
        return default
    return s in ("1", "true", "yes", "on")


def _env_duration_like(name: str, default: str) -> str:
    """
    Возвращает строку-интервал (например, '15s', '1m'). Валидатор намеренно простой:
    ответственность за формат - на вызывающей стороне (Prometheus и т.п.).
    """
    v = os.getenv(name)
    return v.strip() if v else default


def read_env_or_file(name: str, file_name: str) -> str | None:
    """
    Read key:value from plain ENV or from path pointed by *_FILE env var.
    Возвращает None, если не найдено.
    """
    v = os.getenv(name)
    if v:
        return v
    p = os.getenv(file_name)
    if not p:
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


# ----------------------------
# Dataclasses for settings
# ----------------------------

@dataclass(frozen=True)
class Domain:
    root: str


@dataclass(frozen=True)
class Paths:
    tls_certs_dir: str
    service_health_dir: str


@dataclass(frozen=True)
class Timeouts:
    init_timeout_s: int
    retry_interval_s: int
    backoff_factor: float
    max_retry_interval_s: int


@dataclass(frozen=True)
class Consul:
    host: str
    http_port: int
    https_port: int
    # TLS (несекретные пути и флаги)
    tls_enabled: bool
    tls_ca_file: str | None
    tls_cert_file: str | None
    tls_key_file: str | None

    # Производные/утилиты
    def url(self) -> str:
        scheme = "https" if self.tls_enabled else "http"
        port = self.https_port if self.tls_enabled else self.http_port
        return f"{scheme}://{self.host}:{port}"


@dataclass(frozen=True)
class Vault:
    host: str
    http_port: int
    https_port: int
    pki_root_path: str
    pki_int_path: str
    pki_role: str


@dataclass(frozen=True)
class Traefik:
    host: str
    http_port: int
    https_port: int


@dataclass(frozen=True)
class Database:
    host: str
    port: int


@dataclass(frozen=True)
class Observability:
    prometheus_port: int
    grafana_port: int
    scrape_interval: str


@dataclass(frozen=True)
class Policy:
    pki_leaf_ttl_hours: int
    cert_rotate_hours: int
    # Производные поля
    san_list: tuple[str, ...]


@dataclass(frozen=True)
class Context:
    """Паспорт текущего экземпляра сервиса."""
    name: str
    port: int
    tags: tuple[str, ...]
    health_file: str  # абсолютный путь к health-снапшоту этого экземпляра


@dataclass(frozen=True)
class Settings:
    domain: Domain
    paths: Paths
    timeouts: Timeouts
    consul: Consul
    vault: Vault
    traefik: Traefik
    database: Database
    observability: Observability
    policy: Policy
    context: Context

    # TODO: Временная совместимость с плоскими атрибутами (используются в других местах кода) ----
    @property
    def DOMAIN_ROOT(self) -> str: return self.domain.root

    # Consul (для фабрики KV)
    @property
    def CONSUL_HOST(self) -> str: return self.consul.host
    @property
    def CONSUL_HTTP_PORT(self) -> int: return self.consul.http_port
    @property
    def CONSUL_HTTPS_PORT(self) -> int: return self.consul.https_port
    @property
    def CONSUL_TLS_ENABLED(self) -> bool: return self.consul.tls_enabled
    @property
    def CONSUL_TLS_CA_FILE(self) -> str | None: return self.consul.tls_ca_file
    @property
    def CONSUL_TLS_CERT_FILE(self) -> str | None: return self.consul.tls_cert_file
    @property
    def CONSUL_TLS_KEY_FILE(self) -> str | None: return self.consul.tls_key_file

    # Удобный доступ к URL Consul
    def consul_http_url(self) -> str:
        return self.consul.url()


# ----------------------------
# Derived values
# ----------------------------

def _build_default_san_list(domain_root: str) -> List[str]:
    """
    Формирует SAN-список (для server leaf-сертификатов) на основе DOMAIN_ROOT
    и внутренних имён контейнеров. Список минимальный и детерминированный.
    """
    hostnames = [
        ("consul", f"consul.{domain_root}"),
        ("vault", f"vault.{domain_root}"),
        ("traefik", f"traefik.{domain_root}"),
        ("database", f"db.{domain_root}"),
    ]
    san: List[str] = []
    for internal, external in hostnames:
        san.append(external)
        san.append(internal)
    # Уникализировать, сохраняя порядок
    seen = set()
    ordered: List[str] = []
    for x in san:
        if x not in seen:
            ordered.append(x)
            seen.add(x)
    return ordered


def _parse_tags_csv(csv_value: str) -> tuple[str, ...]:
    parts = [p.strip() for p in csv_value.split(",")] if csv_value else []
    return tuple(p for p in parts if p)


# ----------------------------
# Loader & hash
# ----------------------------

def load_settings() -> Settings:
    # Domain
    domain = Domain(root=_env_str("DOMAIN_ROOT", "terminal.speculorg.localhost"))

    # Paths
    paths = Paths(
        tls_certs_dir=_env_str("TLS_CERTS_DIR", "/certs"),
        service_health_dir=_env_str("SERVICE_HEALTH_DIR", "/run/terminal/health"),
    )

    # Timeouts
    timeouts = Timeouts(
        init_timeout_s=_env_int("SERVICE_INIT_TIMEOUT_S", 60),
        retry_interval_s=_env_int("SERVICE_RETRY_INTERVAL_S", 2),
        backoff_factor=_env_float("SERVICE_BACKOFF_FACTOR", 1.5),
        max_retry_interval_s=_env_int("SERVICE_MAX_RETRY_INTERVAL_S", 15),
    )

    # Consul
    consul = Consul(
        host=_env_str("CONSUL_HOST", "consul"),
        http_port=_env_int("CONSUL_HTTP_PORT", 8500),
        https_port=_env_int("CONSUL_HTTPS_PORT", 8501),
        tls_enabled=_env_bool("CONSUL_TLS_ENABLED", False),
        tls_ca_file=_env_str("CONSUL_TLS_CA_FILE", "/etc/ssl/consul/ca.crt"),
        tls_cert_file=_env_str("CONSUL_TLS_CERT_FILE", "/etc/ssl/consul/client.crt"),
        tls_key_file=_env_str("CONSUL_TLS_KEY_FILE", "/etc/ssl/consul/client.key"),
    )

    # Vault
    vault = Vault(
        host=_env_str("VAULT_HOST", "vault"),
        http_port=_env_int("VAULT_HTTP_PORT", 8200),
        https_port=_env_int("VAULT_HTTPS_PORT", 8200),
        pki_root_path=_env_str("VAULT_PKI_ROOT_PATH", "pki"),
        pki_int_path=_env_str("VAULT_PKI_INT_PATH", "pki-int"),
        pki_role=_env_str("VAULT_PKI_ROLE", "terminal-leaf"),
    )

    # Traefik
    traefik = Traefik(
        host=_env_str("TRAEFIK_HOST", "traefik"),
        http_port=_env_int("TRAEFIK_HTTP_PORT", 80),
        https_port=_env_int("TRAEFIK_HTTPS_PORT", 443),
    )

    # Database
    database = Database(
        host=_env_str("DB_HOST", "database"),
        port=_env_int("POSTGRES_PORT", 5432),
    )

    # Observability
    observability = Observability(
        prometheus_port=_env_int("OBS_PROMETHEUS_PORT", 9090),
        grafana_port=_env_int("OBS_GRAFANA_PORT", 3000),
        scrape_interval=_env_duration_like("OBS_SCRAPE_INTERVAL", "15s"),
    )

    # Policy (with derived SAN list)
    san_list = _build_default_san_list(domain.root)
    policy = Policy(
        pki_leaf_ttl_hours=_env_int("PKI_LEAF_TTL_HOURS", 24),
        cert_rotate_hours=_env_int("CERT_ROTATE_HOURS", 24),
        san_list=tuple(san_list),
    )

    # Context (паспорт экземпляра сервиса)
    svc_name = _env_str("SERVICE_NAME", "service")
    svc_port = _env_int("SERVICE_PORT", 0)
    svc_tags = _parse_tags_csv(_env_str("SERVICE_TAGS", ""))
    default_health_path = f"{paths.service_health_dir}/{svc_name}.json"
    health_file = _env_str("SERVICE_HEALTH_FILE", default_health_path)
    context = Context(name=svc_name, port=svc_port, tags=svc_tags, health_file=health_file)

    return Settings(
        domain=domain,
        paths=paths,
        timeouts=timeouts,
        consul=consul,
        vault=vault,
        traefik=traefik,
        database=database,
        observability=observability,
        policy=policy,
        context=context,
    )


def _to_canonical(obj: Any) -> Any:
    """
    Канонизирует dataclass/словарь/список для последующего JSON-дампа:
    - dataclass -> dict
    - dict -> сортированные ключи рекурсивно
    - list/tuple -> список с канонизацией элементов
    - простые типы -> как есть
    """
    if hasattr(obj, "__dataclass_fields__"):
        return _to_canonical(asdict(obj))
    if isinstance(obj, dict):
        return {k: _to_canonical(obj[k]) for k in sorted(obj)}
    if isinstance(obj, (list, tuple)):
        return [_to_canonical(x) for x in obj]
    return obj


def config_hash(settings: Settings) -> str:
    """
    Вычисляет SHA-256 по несекретным кластерным полям SETTINGS.
    ВАЖНО: context (паспорт конкретного экземпляра сервиса) исключается из хэша,
    чтобы CONFIG_HASH отражал именно конфигурацию кластера/окружения.
    """
    canonical = _to_canonical(settings)
    if isinstance(canonical, dict) and "context" in canonical:
        canonical = {k: v for k, v in canonical.items() if k != "context"}
    data = json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


# ----------------------------
# Module-level singletons
# ----------------------------

SETTINGS: Settings = load_settings()
CONFIG_HASH: str = config_hash(SETTINGS)

__all__ = [
    "Settings",
    "SETTINGS",
    "CONFIG_HASH",
    "read_env_or_file",
]
