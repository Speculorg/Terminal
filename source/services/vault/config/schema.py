from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

ROOT_TOKEN_FILENAME: str = "root_vault_token.json"
CONSUL_TOKEN_FILENAME: str = "consul_token_for_vault"

PKI_ROOT_TTL: str = "87600h"
PKI_ROLE_MAX_TTL: str = "720h"

@dataclass(frozen=True)
class LeafSpec:
    common_name: str
    alt_names: str

def build_leaf_svcs(domain_root: str) -> Dict[str, LeafSpec]:
    return {
        "consul":  LeafSpec(common_name=f"consul.{domain_root}",  alt_names="server.dc-1.consul,consul,localhost"),
        "vault":   LeafSpec(common_name=f"vault.{domain_root}",   alt_names="vault,localhost"),
        "traefik": LeafSpec(common_name=f"traefik.{domain_root}", alt_names="traefik,localhost"),
    }

def secrets_kv_minimal() -> Dict[str, Dict[str, str]]:
    return {
        "database": {"user": "speculorg", "pass": "speculpwd"},
        "rabbitmq": {"user": "guest",     "pass": "guest"},
        "keycloak": {"user": "admin",     "pass": "admin"},
    }

def policies_minimal() -> Dict[str, str]:
    return {
        "read-db": (
            'path "secret/data/database" {\n'
            '  capabilities = ["read"]\n'
            '}\n'
        ),
    }

def approles_minimal() -> Dict[str, Dict]:
    return {
        "db-role": {"policies": ["read-db"], "secret_id_ttl": "0s"},
    }
