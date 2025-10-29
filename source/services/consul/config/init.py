from __future__ import annotations
from entities.state_enum import StateEnum

import json, urllib.request, urllib.error
def _http_json(url: str, method: str = "GET", headers: dict | None = None, body: dict | None = None, timeout: int = 5) -> dict:
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    for k,v in (headers or {}).items():
        req.add_header(k, v)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

# === data from schema.py ===
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

def on_bootstrapping(cfg, logger, fs, markers, net):
    host='127.0.0.1'; port=int(cfg.consul.http_port)
    if not net.wait_port(host, port, timeout_ms=int(cfg.fsm.state_initializing_timeout_ms)):
        logger.warn('init.consul.wait_port.timeout', svc=cfg.context.name, details={'port': port})
        return None
    base_url=f'http://{host}:{port}/v1'
    # bootstrap
    if not markers.exists('consul_bootstrap.done'):
        try:
            r=_http_json(f'{base_url}/acl/bootstrap', method='PUT', timeout=max(5,int(cfg.kv.request_timeout_ms/1000)))
            mgmt = r.get('SecretID')
            if mgmt:
                fs.atomic_write_text(f"{cfg.fs.secrets_dir}/root_consul_token.json", json.dumps(r, ensure_ascii=False, separators=(',',':')))
                markers.set('consul_bootstrap.done')
                logger.info('init.consul.bootstrap', svc=cfg.context.name, details={'ok': True})
        except Exception as e:
            logger.error('init.consul.bootstrap.error', svc=cfg.context.name, details={'error': str(e)})
            return None
    # policies and tokens
    if not markers.exists('consul_tokens.done'):
        try:
            pols = policies_minimal()
        except Exception as e:
            logger.error('init.consul.schema.error', svc=cfg.context.name, details={'error': str(e)})
            return None
        try:
            tok_json = fs.atomic_read_text(f"{cfg.fs.secrets_dir}/root_consul_token.json")
            mgmt_token = json.loads(tok_json).get('SecretID')
        except Exception:
            mgmt_token = cfg.context.consul_token or None
        if not mgmt_token:
            logger.warn('init.consul.no_mgmt_token', svc=cfg.context.name, details={})
            return None
        H={'X-Consul-Token': mgmt_token}
        for key, spec in pols.items():
            try:
                body={'Name': spec.name, 'Rules': spec.rules}
                _http_json(f'{base_url}/acl/policy', method='PUT', headers=H, body=body, timeout=max(5,int(cfg.kv.request_timeout_ms/1000)))
                logger.info('init.consul.policy.upsert', svc=cfg.context.name, details={'name': spec.name})
            except Exception as e:
                logger.warn('init.consul.policy.error', svc=cfg.context.name, details={'name': spec.name, 'error': str(e)})
        for key, spec in pols.items():
            try:
                body={'Description': spec.desc, 'Policies':[{'Name': spec.name}]}
                r=_http_json(f'{base_url}/acl/token', method='PUT', headers=H, body=body, timeout=max(5,int(cfg.kv.request_timeout_ms/1000)))
                sid = r.get('SecretID')
                if sid:
                    fs.atomic_write_text(f"{cfg.fs.secrets_dir}/{spec.filename}", sid)
                    logger.info('init.consul.token.issue', svc=cfg.context.name, details={'file': spec.filename})
            except Exception as e:
                logger.warn('init.consul.token.error', svc=cfg.context.name, details={'policy': spec.name, 'error': str(e)})
        markers.set('consul_tokens.done')
    return StateEnum.INITIALIZING