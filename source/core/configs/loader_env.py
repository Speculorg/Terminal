from __future__ import annotations
import os
from typing import Dict, Tuple
from .model import (
    Model, GlobalSection, ContextSection, ConsulSection, VaultSection, TraefikSection,
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

def _overlay(base_env: Dict[str, str], over_env: Dict[str, str]) -> Dict[str, str]:
    merged = dict(base_env)
    for k, v in over_env.items():
        merged[k] = str(v)
    return merged

def _pick_configs_env_path() -> str | None:
    p = os.environ.get("CONFIGS_ENV_PATH")
    if p and os.path.isfile(p):
        return p
    # стандартные места
    for candidate in ("/config/configs.env", "./configs.env", "/app/configs.env"):
        if os.path.isfile(candidate):
            return candidate
    return None

def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]

def _read_token_file(path: str | None) -> str | None:
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def load_model() -> Tuple[Model, Dict[str, str]]:
    file_path = _pick_configs_env_path()
    file_env = _read_env_file(file_path) if file_path else {}
    merged = _overlay(file_env, dict(os.environ))

    global_ = GlobalSection(
        domain_root=merged.get("GLOBAL_DOMAIN_ROOT", "terminal.local"),
        version=merged.get("GLOBAL_VERSION", "0.0.0-dev"),
    )

    context = ContextSection(
        name=merged.get("SERVICE_NAME", "default-name-service"),
        port=int(merged.get("SERVICE_PORT", "0") or "0"),
        tags=_parse_tags(merged.get("SERVICE_TAGS")),
        consul_token=_read_token_file(merged.get("CONSUL_HTTP_TOKEN_FILE")),
    )

    consul = ConsulSection(
        host=merged.get("CONSUL_HOST", "consul"),
        http_port=int(merged.get("CONSUL_HTTP_PORT", "8500") or "8500"),
        https_port=int(merged.get("CONSUL_HTTPS_PORT", "8501") or "8501"),
    )

    vault = VaultSection(
        host=merged.get("VAULT_HOST", "vault"),
        http_port=int(merged.get("VAULT_HTTP_PORT", "8200") or "8200"),
        https_port=int(merged.get("VAULT_HTTPS_PORT", "8200") or "8200"),
        pki_root_path=merged.get("VAULT_PKI_ROOT_PATH", "pki-root"),
        pki_int_path=merged.get("VAULT_PKI_INT_PATH", "pki-int"),
        pki_role=merged.get("VAULT_PKI_ROLE", "terminal-leaf"),
    )

    traefik = TraefikSection(
        host=merged.get("TRAEFIK_HOST", "traefik"),
        http_port=int(merged.get("TRAEFIK_HTTP_PORT", "8080") or "8080"),
        https_port=int(merged.get("TRAEFIK_HTTPS_PORT", "8443") or "8443"),
    )

    logging = LoggingSection(
        level=merged.get("LOGGING_LEVEL", "INFO"),
        correlation_id_header=merged.get("LOGGING_CORRELATION_ID_HEADER", "X-Request-ID"),
        generate_correlation_if_missing=merged.get("LOGGING_GENERATE_CORRELATION_IF_MISSING", "true").lower() == "true",
        correlation_id_len_max=int(merged.get("LOGGING_CORRELATION_ID_LEN_MAX", "64") or "64"),
    )

    metrics = MetricsSection(
        host=merged.get("METRICS_HOST", "0.0.0.0"),
        path=merged.get("METRICS_PATH", "/metrics"),
        port=int(merged.get("METRICS_PORT", "8000") or "8000"),
    )

    fs = FSSection(
        certs_dir=merged.get("FS_CERTS_DIR", "/certs"),
        secrets_dir=merged.get("FS_SECRETS_DIR", "/secrets"),
    )

    tls = TLSSection(
        certs_rotate_hours=int(merged.get("TLS_CERTS_ROTATE_HOURS", "168") or "168"),
        reloader_strategy=merged.get("TLS_RELOADER_STRATEGY", "SSL_CTX"),
        watch_debounce_ms=int(merged.get("TLS_WATCH_DEBOUNCE_MS", "300") or "300"),
        watch_poll_interval_ms=int(merged.get("TLS_WATCH_POLL_INTERVAL_MS", "500") or "500"),
    )

    kv = KVSection(
        cas_backoff_factor=int(merged.get("KV_CAS_BACKOFF_FACTOR", "2") or "2"),
        cas_max_retries=int(merged.get("KV_CAS_MAX_RETRIES", "5") or "5"),
        request_timeout_ms=int(merged.get("KV_REQUEST_TIMEOUT_MS", "5000") or "5000"),
    )

    fsm = FSMSection(
        state_bootstrapping_timeout_ms=int(merged.get("FSM_STATE_BOOTSTRAPPING_TIMEOUT_MS", "5000") or "5000"),
        state_initializing_timeout_ms=int(merged.get("FSM_STATE_INITIALIZING_TIMEOUT_MS", "15000") or "15000"),
        state_securing_timeout_ms=int(merged.get("FSM_STATE_SECURING_TIMEOUT_MS", "10000") or "10000"),
        state_tls_transition_timeout_ms=int(merged.get("FSM_STATE_TLS_TRANSITION_TIMEOUT_MS", "5000") or "5000"),
        state_registering_timeout_ms=int(merged.get("FSM_STATE_REGISTERING_TIMEOUT_MS", "5000") or "5000"),
        state_running_tick_timeout_ms=int(merged.get("FSM_STATE_RUNNING_TICK_TIMEOUT_MS", "5000") or "5000"),
        state_publish_min_interval_ms=int(merged.get("FSM_STATE_PUBLISH_MIN_INTERVAL_MS", "5000") or "5000"),
        degraded_recovery_window_ms=int(merged.get("FSM_DEGRADED_RECOVERY_WINDOW_MS", "60000") or "60000"),
        degraded_transition_window_ms=int(merged.get("FSM_DEGRADED_TRANSITION_WINDOW_MS", "30000") or "30000"),
        degraded_min_duration_ms=int(merged.get("FSM_DEGRADED_MIN_DURATION_MS", "5000") or "5000"),
    )

    registrar = RegistrarSection(
        deregister_critical_service_after_sec=int(merged.get("REGISTRAR_DEREGISTER_CRITICAL_SERVICE_AFTER_SEC", "45") or "45"),
        heartbeat_period_sec=int(merged.get("REGISTRAR_HEARTBEAT_PERIOD_SEC", "7") or "7"),
        ttl_sec=int(merged.get("REGISTRAR_TTL_SEC", "15") or "15"),
        reregistration_cooldown_sec=int(merged.get("REGISTRAR_REREGISTRATION_COOLDOWN_SEC", "15") or "15"),
        max_rereg_attempts_per_window=int(merged.get("REGISTRAR_MAX_REREG_ATTEMPTS_PER_WINDOW", "5") or "5"),
    )

    model = Model(
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
