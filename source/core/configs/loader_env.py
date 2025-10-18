from __future__ import annotations
import os
from typing import Dict, Tuple
from .model import (
    ConfigModel, GlobalSection, ContextSection, ConsulSection, VaultSection, TraefikSection,
    LoggingSection, MetricsSection, FSSection, TLSSection, KVSection, FSMSection, RegistrarSection
)

def _read_env_file(path: str) -> Dict[str, str]:
    data: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return data

def _pick_configs_env_path() -> str:
    candidates = [
        os.environ.get("CONFIGS_ENV_PATH"),
        "/config/configs.env",
        "./config/configs.env",
        "./configs.env",
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return ""

def _overlay(base: Dict[str, str], top: Dict[str, str]) -> Dict[str, str]:
    out = dict(base)
    out.update(top)
    return out

def _split_tags(raw: str) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]

def _read_consul_token_from_file(path: str) -> str | None:
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def load_model() -> Tuple[ConfigModel, Dict[str, str]]:
    file_path = _pick_configs_env_path()
    file_env = _read_env_file(file_path) if file_path else {}
    merged = _overlay(file_env, dict(os.environ))

    # Sections
    global_ = GlobalSection(
        domain_root=merged.get("GLOBAL_DOMAIN_ROOT", "localdomain"),
        version=merged.get("GLOBAL_VERSION", "0.0.0"),
    )

    context = ContextSection(
        name=merged.get("SERVICE_NAME", "default-name-service"),
        port=int(merged.get("SERVICE_PORT", "0")),
        tags=_split_tags(merged.get("SERVICE_TAGS", "")),
        consul_token=_read_consul_token_from_file(merged.get("CONSUL_HTTP_TOKEN_FILE", "")),
    )

    consul = ConsulSection(
        host=merged.get("CONSUL_HOST", "consul"),
        http_port=int(merged.get("CONSUL_HTTP_PORT", "8500")),
        https_port=int(merged.get("CONSUL_HTTPS_PORT", "8501")),
        scheme=merged.get("CONSUL_SCHEME", "http"),
    )

    vault = VaultSection(
        host=merged.get("VAULT_HOST", "vault"),
        http_port=int(merged.get("VAULT_HTTP_PORT", "8200")),
        https_port=int(merged.get("VAULT_HTTPS_PORT", "8200")),
        scheme=merged.get("VAULT_SCHEME", "http"),
    )

    traefik = TraefikSection(
        host=merged.get("TRAEFIK_HOST", "traefik"),
        https_port=int(merged.get("TRAEFIK_HTTPS_PORT", "8443")),
    )

    logging = LoggingSection(
        level=merged.get("LOGGING_LEVEL", "INFO"),
    )

    metrics = MetricsSection(
        path=merged.get("METRICS_PATH", "/metrics"),
        port=int(merged.get("METRICS_PORT", "9090")),
    )

    fs = FSSection(
        root_dir=merged.get("FS_ROOT_DIR", "/app"),
        markers_dir=merged.get("FS_MARKERS_DIR", "/app/fs/markers"),
        secrets_dir=merged.get("FS_SECRETS_DIR", "/app/fs/secrets"),
        certs_dir=merged.get("FS_CERTS_DIR", "/app/fs/certs"),
    )

    tls = TLSSection(
        cert_name=merged.get("TLS_CERT_NAME", "traefik"),
        cert_path=merged.get("TLS_CERT_PATH", "/app/fs/certs/traefik.crt"),
        key_path=merged.get("TLS_KEY_PATH", "/app/fs/certs/traefik.key"),
        chain_path=merged.get("TLS_FULLCHAIN_PATH", "/app/fs/certs/traefik.fullchain"),
        ca_path=merged.get("TLS_CA_PATH", "/app/fs/certs/ca.crt"),
        certs_rotate_hours=int(merged.get("TLS_CERTS_ROTATE_HOURS", "24")),
    )

    kv = KVSection(
        request_timeout_ms=int(merged.get("KV_REQUEST_TIMEOUT_MS", "2000")),
    )

    fsm = FSMSection(
        state_bootstrapping_timeout_ms=int(merged.get("FSM_BOOTSTRAPPING_TIMEOUT_MS", "15000")),
        state_initializing_timeout_ms=int(merged.get("FSM_INITIALIZING_TIMEOUT_MS", "30000")),
        state_securing_timeout_ms=int(merged.get("FSM_SECURING_TIMEOUT_MS", "30000")),
        state_tls_transition_timeout_ms=int(merged.get("FSM_TLS_TRANSITION_TIMEOUT_MS", "30000")),
        state_registering_timeout_ms=int(merged.get("FSM_REGISTERING_TIMEOUT_MS", "15000")),
    )

    registrar = RegistrarSection(
        enabled=(merged.get("REGISTRAR_ENABLED", "true").lower() == "true"),
    )

    model = ConfigModel(
        global_=global_,
        context=context,
        consul=consul,
        vault=vault,
        traefik=traefik,
        logging=logging,
        metrics=metrics,
        fs=fs,
        tls=tls,
        kv=kv,
        fsm=fsm,
        registrar=registrar,
    )
    return model, merged
