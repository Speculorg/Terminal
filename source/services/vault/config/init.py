from __future__ import annotations
from entities.state_enum import StateEnum
from dataclasses import dataclass
from typing import Dict
import json, urllib.request, urllib.error

ROOT_TOKEN_FILENAME: str = "root_vault_token.json"
CONSUL_TOKEN_FILENAME: str = "consul_token_for_vault"

PKI_ROOT_TTL: str = "87600h"
PKI_ROLE_MAX_TTL: str = "720h"


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

def on_initializing(cfg, logger, fs, markers, net):
    host='127.0.0.1'; port=int(cfg.vault.http_port)
    if not net.wait_port(host, port, timeout_ms=int(cfg.fsm.state_initializing_timeout_ms)):
        logger.warn('init.vault.wait_port.timeout', svc=cfg.context.name, details={'port': port})
        return None
    base_url=f'http://{host}:{port}/v1'
    try:
        st=_http_json(f'{base_url}/sys/init', timeout=max(5,int(cfg.kv.request_timeout_ms/1000)))
        initialized = bool(st.get('initialized'))
    except Exception:
        initialized=False
    unseal_key=None; root_token=None
    if not markers.exists('vault_init.done'):
        if not initialized:
            try:
                r=_http_json(f'{base_url}/sys/init', method='PUT', body={'secret_shares':1,'secret_threshold':1}, timeout=max(5,int(cfg.kv.request_timeout_ms/1000)))
                unseal_key = r.get('keys_base64', [None])[0] or r.get('keys', [None])[0]
                root_token = r.get('root_token')
                if root_token:
                    fs.atomic_write_text(f"{cfg.fs.secrets_dir}/root_vault_token.json", json.dumps(r, ensure_ascii=False, separators=(',',':')))
                    markers.set('vault_init.done')
                    logger.info('init.vault.init', svc=cfg.context.name, details={'ok': True})
            except Exception as e:
                logger.error('init.vault.init.error', svc=cfg.context.name, details={'error': str(e)})
                return None
    if not markers.exists('vault_unseal.done'):
        try:
            if unseal_key is None:
                try:
                    init_json = fs.atomic_read_text(f"{cfg.fs.secrets_dir}/root_vault_token.json")
                    init_obj = json.loads(init_json)
                    unseal_key = init_obj.get('keys_base64', [None])[0] or init_obj.get('keys', [None])[0]
                    root_token = init_obj.get('root_token', None)
                except Exception:
                    pass
            if unseal_key:
                _http_json(f'{base_url}/sys/unseal', method='PUT', body={'key': unseal_key}, timeout=max(5,int(cfg.kv.request_timeout_ms/1000)))
                markers.set('vault_unseal.done')
                logger.info('init.vault.unseal', svc=cfg.context.name, details={'ok': True})
        except Exception as e:
            logger.error('init.vault.unseal.error', svc=cfg.context.name, details={'error': str(e)})
            return None
    return StateEnum.SECURING

def on_securing(cfg, logger, fs, markers, net):
    host='127.0.0.1'; port=int(cfg.vault.http_port)
    base_url=f'http://{host}:{port}/v1'
    try:
        init_json = fs.atomic_read_text(f"{cfg.fs.secrets_dir}/root_vault_token.json")
        root_token = json.loads(init_json).get('root_token')
    except Exception:
        root_token=None
    if not root_token:
        logger.warn('init.vault.no_root_token', svc=cfg.context.name, details={})
        return None
    H={'X-Vault-Token': root_token}
    try: _http_json(f'{base_url}/sys/mounts/pki', method='POST', headers=H, body={'type':'pki'}, timeout=10)
    except Exception: pass
    try: _http_json(f'{base_url}/sys/mounts/pki/tune', method='POST', headers=H, body={'max_lease_ttl':'87600h'}, timeout=10)
    except Exception: pass
    try: _http_json(f"{base_url}/pki/root/generate/internal", method='POST', headers=H, body={'common_name': cfg.domain_root, 'ttl':'87600h'}, timeout=10)
    except Exception: pass
    try: _http_json(f'{base_url}/pki/roles/leaf', method='POST', headers=H, body={'allowed_domains': cfg.domain_root, 'allow_subdomains': True, 'max_ttl':'720h'}, timeout=10)
    except Exception: pass
    wrote_any=False
    try:
        leaves = build_leaf_svcs(cfg.domain_root)
    except Exception:
        leaves = {}
    for name, leaf in (leaves or {}).items():
        try:
            body={'common_name': leaf.common_name, 'alt_names': leaf.alt_names, 'ttl':'720h'}
            r=_http_json(f'{base_url}/pki/issue/leaf', method='POST', headers=H, body=body, timeout=10)
            cert = r.get('data',{}).get('certificate')
            key = r.get('data',{}).get('private_key')
            ca = r.get('data',{}).get('issuing_ca')
            if cert and key and ca:
                fs.atomic_write_text(f"{cfg.fs.certs_dir}/{name}.crt", cert)
                fs.atomic_write_text(f"{cfg.fs.certs_dir}/{name}.key", key, mode=0o640)
                if not markers.exists('vault_initial_pem.done'):
                    fs.atomic_write_text(f"{cfg.fs.certs_dir}/ca.crt", ca)
                    markers.set('vault_initial_pem.done')
                wrote_any=True
                logger.info('init.vault.pki.leaf', svc=cfg.context.name, details={'name': name})
        except Exception as e:
            logger.warn('init.vault.pki.leaf.error', svc=cfg.context.name, details={'name': name, 'error': str(e)})
    if wrote_any:
        markers.set('vault_pki.done')
        logger.info('init.vault.pki.done', svc=cfg.context.name, details={})
    return StateEnum.TLS_TRANSITION