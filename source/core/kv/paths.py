# source/core/kv/paths.py

from __future__ import annotations

"""
Единая точка правды для KV-ключей (SoT) в Consul KV.
Никаких "магических строк" по коду — только эти константы и фабрики.

Принципы:
- Префиксы строго фиксированы: marker/*, status/*, certs/*, config/*.
- Маркеры — минимальные флаги-факты (идемпотентные).
- Статусы/heartbeat — «живые» значения с временными метками.
- Сертификаты — только публичные PEM/версия.
- Конфиги — несекретные параметры (глобальные/сервисные).
"""

# ----------------------------- Базовые префиксы -----------------------------
MARKER_PREFIX = "marker"
STATUS_PREFIX = "status"
CERTS_PREFIX  = "certs"
CONFIG_PREFIX = "config"

# ----------------------------- Фабрики ключей -------------------------------

def marker_svc_flag(svc: str, flag: str) -> str:
    """marker/<svc>/<flag>"""
    return f"{MARKER_PREFIX}/{svc}/{flag}"

def status_snapshot_key(svc: str) -> str:
    """status/<svc>/status"""
    return f"{STATUS_PREFIX}/{svc}/status"

def status_heartbeat_key(svc: str) -> str:
    """status/<svc>/heartbeat"""
    return f"{STATUS_PREFIX}/{svc}/heartbeat"

def certs_service_crt(svc: str) -> str:
    """certs/<svc>.crt (публичный fullchain PEM)"""
    return f"{CERTS_PREFIX}/{svc}.crt"

def config_global_key(name: str) -> str:
    """config/global/<name>"""
    return f"{CONFIG_PREFIX}/global/{name}"

def config_service_key(svc: str, name: str) -> str:
    """config/<svc>/<name>"""
    return f"{CONFIG_PREFIX}/{svc}/{name}"

# ----------------------------- Частые ключи: certs --------------------------

CERTS_CA_PEM   = f"{CERTS_PREFIX}/ca.crt"
CERTS_VERSION  = f"{CERTS_PREFIX}/version"
CERTS_STATUS   = f"{MARKER_PREFIX}/vault/certs_status"  # JSON-статус PKI/ротации (best-effort)

# ----------------------------- Частые ключи: config -------------------------

CONFIG_GLOBAL_DOMAIN_ROOT = config_global_key("domain_root")
CONFIG_GLOBAL_CONFIG_HASH = config_global_key("config_hash")

# ----------------------------- Маркеры: Consul ------------------------------

M_CONSUL_INITIALIZED      = marker_svc_flag("consul", "initialized")
M_CONSUL_MTLS_READY       = marker_svc_flag("consul", "mtls_ready")
M_CONSUL_CATALOG_SYNCED   = marker_svc_flag("consul", "catalog_synchronized")
M_CONSUL_REGISTERED       = marker_svc_flag("consul", "registered")

# ----------------------------- Маркеры: Vault -------------------------------

M_VAULT_INITIALIZED       = marker_svc_flag("vault", "initialized")
M_VAULT_PKI_ROOT_READY    = marker_svc_flag("vault", "pki_root_ready")
M_VAULT_PKI_INT_READY     = marker_svc_flag("vault", "pki_int_ready")
M_VAULT_PKI_LEAF_READY    = marker_svc_flag("vault", "pki_leaf_ready")
# Статус/версия сертификатов публикуется в CERTS_STATUS и CERTS_VERSION

# ----------------------------- Маркеры: Traefik -----------------------------

M_TRAEFIK_INITIALIZED     = marker_svc_flag("traefik", "initialized")
M_TRAEFIK_REGISTERED      = marker_svc_flag("traefik", "registered")
M_TRAEFIK_CONSULCAT_OK    = marker_svc_flag("traefik", "consul_catalog_available")

# ----------------------------- Вспомогательные фабрики ----------------------

def certs_for_services(*services: str) -> dict[str, str]:
    """
    Удобный билдер набора ключей certs/<svc>.crt по списку сервисов.
    Пример: certs_for_services("consul", "vault", "traefik")
    """
    return {svc: certs_service_crt(svc) for svc in services}
