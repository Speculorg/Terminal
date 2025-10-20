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
                if "=" in line:
                    k, v = line.split("=", 1)
                    data[k.strip()] = v.strip()
    except FileNotFoundError:
        ...
        pass
    return data

def _pick_configs_env_path() -> str | None:
    # приоритет переменной CONFIGS_ENV_PATH, иначе стандартный путь
    return os.environ.get("CONFIGS_ENV_PATH", "/app/configs.env")

def _overlay(base: Dict[str, str], override: Dict[str, str]) -> Dict[str, str]:
    merged = dict(base)
    merged.update(override or {})
    return merged

def _split_tags(raw: str) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]

def _read_consul_token_from_file(path: str | None) -> str | None:
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

    global_ = GlobalSection(
        domain_root=merged.get("GLOBAL_DOMAIN_ROOT", "terminal.local"),
        version=merged.get("GLOBAL_VERSION", "0.0.0-dev"),
    )

    context = ContextSection(
        name=merged.get("SERVICE_NAME", "default-name-service"),
        port=int(merged.get("SERVICE_PORT", "0")),
        tags=_split_tags(merged.get("SERVICE_TAGS", "")),
        consul_token=_read_consul_token_from_file(merged.get("CONSUL_HTTP_TOKEN_FILE")),
    )

    consul = ConsulSection(
        host=merged.get("CONSUL_HOST", "consul"),
        http_port=int(merged.get("CONSUL_HTTP_PORT", "8500")),
        https_port=int(merged.get("CONSUL_HTTPS_PORT", "8501")),
    )

    vault = VaultSection(
        host=merged.get("VAULT_HOST", "vault"),
        http_port=int(merged.get("VAULT_HTTP_PORT", "8200")),
        https_port=int(merged.get("VAULT_HTTPS_PORT", "8201")),
        pki_root_path=merged.get("VAULT_PKI_ROOT_PATH", "pki-root"),
        pki_int_path=merged.get("VAULT_PKI_INT_PATH", "pki-int"),
        pki_role=merged.get("VAULT_PKI_ROLE", "terminal-leaf"),
    )

    traefik = TraefikSection(
        host=merged.get("TRAEFIK_HOST", "traefik"),
        https_port=int(merged.get("TRAEFIK_HTTPS_PORT", "8443")),
    )

    logging = LoggingSection(
        level=merged.get("LOGGING_LEVEL", "INFO"),
        correlation_id_header=merged.get("LOGGING_CORRELATION_ID_HEADER", "X-Request-ID"),
        generate_correlation_if_missing=(merged.get("LOGGING_GENERATE_CORRELATION_IF_MISSING", "true").lower()=="true"),
        correlation_id_len_max=int(merged.get("LOGGING_CORRELATION_ID_LEN_MAX", "64")),
    )

    metrics = MetricsSection(
        path=merged.get("METRICS_PATH", "/metrics"),
        port=int(merged.get("METRICS_PORT", "8000")),
    )

    fs = FSSection(
        root_dir=merged.get("FS_ROOT_DIR", "/app"),
        markers_dir=merged.get("FS_MARKERS_DIR", "/app/fs/markers"),
        secrets_dir=merged.get("FS_SECRETS_DIR", "/app/fs/secrets"),
        certs_dir=merged.get("FS_CERTS_DIR", "/app/fs/certs"),
    )

    tls = TLSSection(
        cert_name=merged.get("TLS_CERT_NAME", merged.get("SERVICE_NAME", "svc")),
        cert_path=merged.get("TLS_CERT_PATH", "/app/fs/certs/cert.pem"),
        key_path=merged.get("TLS_KEY_PATH", "/app/fs/certs/privkey.pem"),
        chain_path=merged.get("TLS_FULLCHAIN_PATH", "/app/fs/certs/fullchain.pem"),
        ca_path=merged.get("TLS_CA_PATH", "/app/fs/certs/ca.crt"),
        certs_rotate_hours=int(merged.get("TLS_CERTS_ROTATE_HOURS", "168")),
        reloader_strategy=merged.get("TLS_RELOADER_STRATEGY", "SSL_CTX"),
        watch_debounce_ms=int(merged.get("TLS_WATCH_DEBOUNCE_MS", "300")),
        watch_poll_interval_ms=int(merged.get("TLS_WATCH_POLL_INTERVAL_MS", "500")),
    )

    kv = KVSection(
        request_timeout_ms=int(merged.get("KV_REQUEST_TIMEOUT_MS", "5000")),
        cas_backoff_factor=int(merged.get("KV_CAS_BACKOFF_FACTOR", "2")),
        cas_max_retries=int(merged.get("KV_CAS_MAX_RETRIES", "5")),
    )

    fsm = FSMSection(
        state_starting_timeout_ms=int(merged.get("FSM_STARTING_TIMEOUT_MS", "10000")),
        state_bootstrapping_timeout_ms=int(merged.get("FSM_BOOTSTRAPPING_TIMEOUT_MS", "5000")),
        state_initializing_timeout_ms=int(merged.get("FSM_INITIALIZING_TIMEOUT_MS", "15000")),
        state_securing_timeout_ms=int(merged.get("FSM_SECURING_TIMEOUT_MS", "10000")),
        state_tls_transition_timeout_ms=int(merged.get("FSM_TLS_TRANSITION_TIMEOUT_MS", "5000")),
        state_registering_timeout_ms=int(merged.get("FSM_REGISTERING_TIMEOUT_MS", "5000")),
        state_running_tick_timeout_ms=int(merged.get("FSM_RUNNING_TICK_TIMEOUT_MS", "5000")),
        state_publish_min_interval_ms=int(merged.get("FSM_PUBLISH_MIN_INTERVAL_MS", "5000")),
        degraded_recovery_window_ms=int(merged.get("FSM_DEGRADED_RECOVERY_WINDOW_MS", "60000")),
        degraded_transition_window_ms=int(merged.get("FSM_DEGRADED_TRANSITION_WINDOW_MS", "30000")),
        degraded_min_duration_ms=int(merged.get("FSM_DEGRADED_MIN_DURATION_MS", "5000")),
    )

    registrar = RegistrarSection(
        ttl_sec=int(merged.get("REGISTRAR_TTL_SEC", "15")),
        heartbeat_period_sec=int(merged.get("REGISTRAR_HEARTBEAT_PERIOD_SEC", "7")),
        deregister_critical_service_after_sec=int(merged.get("REGISTRAR_DEREGISTER_CRITICAL_SERVICE_AFTER_SEC", "45")),
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
