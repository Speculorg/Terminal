from __future__ import annotations
from entities import StateEnum

class IRunProfile:
    stage_gates: dict
    start_cmd: dict

class ConsulRunProfile(IRunProfile):
    stage_gates = {
        StateEnum.BOOTSTRAPPING: ["consul_bootstrap.done", "consul_tokens.done"],
        StateEnum.SECURING: ["vault_initial_pem.done"],
        StateEnum.REGISTERING: ["consul_tokens.done", "vault_initial_pem.done"],
        StateEnum.TLS_TRANSITION: ["vault_initial_pem.done"],
    }
    start_cmd = {
        "http": ["consul", "agent", "-config-file=/config/consul_http.hcl"],
        "https": ["consul", "agent", "-config-file=/config/consul_https.hcl"],
    }

class TraefikRunProfile(IRunProfile):
    stage_gates = {
        StateEnum.SECURING: ["vault_initial_pem.done"],
        StateEnum.REGISTERING: ["consul_tokens.done"],
        StateEnum.TLS_TRANSITION: ["vault_initial_pem.done"],
    }
    start_cmd = {
        "https": ["traefik", "--configFile=/config/traefik.yml"],
    }

class VaultRunProfile(IRunProfile):
    stage_gates = {
        StateEnum.BOOTSTRAPPING: ["consul_bootstrap.done", "consul_tokens.done", "vault_init.done"],
        StateEnum.INITIALIZING: ["vault_unseal.done"],
        StateEnum.SECURING: ["vault_pki.done", "vault_initial_pem.done"],
        StateEnum.REGISTERING: ["consul_tokens.done", "vault_pki.done", "vault_initial_pem.done"],
        StateEnum.TLS_TRANSITION: ["vault_pki.done", "vault_initial_pem.done"],
    }
    start_cmd = {
        "http": ["vault", "server", "-config=/config/vault_http.hcl"],
        "https": ["vault", "server", "-config=/config/vault_https.hcl"],
    }
