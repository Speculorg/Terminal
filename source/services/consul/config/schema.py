from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

ROOT_TOKEN_FILENAME: str = "root_consul_token.json"
AGENT_TOKEN_FILENAME: str = "consul_token_for_consul"
VAULT_TOKEN_FILENAME: str = "consul_token_for_vault"
TRAEFIK_TOKEN_FILENAME: str = "consul_token_for_traefik"

@dataclass(frozen=True)
class PolicySpec:
    name: str
    rules: str
    token_filename: str
    desc: str

def policies_minimal() -> Dict[str, PolicySpec]:
    return {
        "agent": PolicySpec(
            name="agent-policy",
            desc="token-for-consul-agent",
            token_filename=AGENT_TOKEN_FILENAME,
            rules=(
                'agent            "" { policy = "write" }\n'
                'node_prefix      "" { policy = "write" }\n'
                'service_prefix   "" { policy = "read"  }\n'
                'session_prefix   "" { policy = "write" }\n'
            ),
        ),
        "vault": PolicySpec(
            name="vault-policy",
            desc="token-for-vault",
            token_filename=VAULT_TOKEN_FILENAME,
            rules=(
                'key_prefix "vault/"                   { policy = "write" }\n'
                'session_prefix ""                     { policy = "write" }\n'
                'key_prefix "certs/"                   { policy = "write" }\n'
                'key_prefix "marker/vault/"            { policy = "write" }\n'
                'key_prefix "config/global/"           { policy = "read"  }\n'
                'key_prefix "status/"                  { policy = "read"  }\n'
                'service "vault"                       { policy = "write" }\n'
                'node_prefix ""                        { policy = "read"  }\n'
                'query_prefix ""                       { policy = "read"  }\n'
            ),
        ),
        "traefik": PolicySpec(
            name="traefik-policy",
            desc="token-for-traefik",
            token_filename=TRAEFIK_TOKEN_FILENAME,
            rules=(
                'key_prefix "certs/"                     { policy = "read"  }\n'
                'key_prefix "marker/vault/certs_status"  { policy = "read"  }\n'
                'key_prefix "config/global/"             { policy = "read"  }\n'
                'key_prefix "marker/traefik/"            { policy = "write" }\n'
                'key_prefix "status/traefik/"            { policy = "write" }\n'
                'key_prefix "markers/traefik/"           { policy = "read"  }\n'
                'service "traefik"                        { policy = "write" }\n'
                'node_prefix ""                           { policy = "read"  }\n'
                'query_prefix ""                          { policy = "read"  }\n'
                'service_prefix ""                        { policy = "read"  }\n'
            ),
        ),
    }
