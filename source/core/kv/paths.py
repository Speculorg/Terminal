# source\core\kv\paths.py

"""
core.kv.paths
Единый нейминг ключей KV.
"""

from __future__ import annotations
from typing import Final

# ---- marker (факты/вехи) ----
MARKER: Final[str] = "marker"
LEGACY_MARKERS: Final[str] = "markers"  # для чтения (совместимость)

# consul
M_CONSUL_INITIALIZED         = f"{MARKER}/consul/initialized"
M_CONSUL_MTLS_READY          = f"{MARKER}/consul/mtls_ready"
M_CONSUL_CATALOG_SYNCED      = f"{MARKER}/consul/catalog_synchronized"

# vault
M_VAULT_INITIALIZED          = f"{MARKER}/vault/initialized"
M_VAULT_PKI_ROOT_READY       = f"{MARKER}/vault/pki_root_ready"
M_VAULT_PKI_INT_READY        = f"{MARKER}/vault/pki_int_ready"
M_VAULT_PKI_LEAF_READY       = f"{MARKER}/vault/pki_leaf_ready"
M_VAULT_CERTS_STATUS         = f"{MARKER}/vault/certs_status"  # JSON {"version":..,"updated_at":..,"meta":...}

# traefik
M_TRAEFIK_INITIALIZED        = f"{MARKER}/traefik/initialized"
M_TRAEFIK_REGISTERED         = f"{MARKER}/traefik/registered"
M_TRAEFIK_CONSUL_CATALOG_OK  = f"{MARKER}/traefik/consul_catalog_available"

# ---- status (статусы/фазы сервисов) ----
STATUS: Final[str] = "status"
def status_key(svc: str) -> str:
    return f"{STATUS}/{svc.strip()}"

# ---- certs (публичные сертификаты) ----
CERTS: Final[str] = "certs"
CERTS_CA_PEM                  = f"{CERTS}/ca.crt"
def certs_svc_pem(svc: str) -> str:
    return f"{CERTS}/{svc.strip()}.crt"
CERTS_VERSION                 = f"{CERTS}/version"  # int|hash строкой
CERTS_STATUS                  = M_VAULT_CERTS_STATUS

# ---- config (несекретные конфиги) ----
CONFIG: Final[str] = "config"
CONFIG_GLOBAL_DOMAIN_ROOT     = f"{CONFIG}/global/domain_root"
CONFIG_GLOBAL_CONFIG_HASH     = f"{CONFIG}/global/config_hash"
CONFIG_GLOBAL_CONFIG_VERS     = f"{CONFIG}/global/config_versions"
def config_svc_key(svc: str, name: str) -> str:
    return f"{CONFIG}/{svc.strip()}/{name.strip()}"
