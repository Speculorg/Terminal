from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from _base import BaseConfigs

from .model import (
    Model,
    GlobalSection,
    ContextSection,
    ConsulSection,
    VaultSection,
    TraefikSection,
    LoggingSection,
    MetricsSection,
    FSSection,
    TLSSection,
    KVSection,
    FSMSection,
    RegistrarSection,
)


def _read_env_file(path: str) -> Dict[str, str]:
    data: Dict[str, str] = {}
    try:
        p = Path(path)
        if not p.exists():
            return data
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    except Exception:
        # configs.env не должен ломать запуск; ошибки будут проявлены позже через диагностику/логи
        return data
    return data


def _merge_env(file_env: Dict[str, str]) -> Dict[str, str]:
    merged = dict(file_env)
    merged.update({k: v for k, v in os.environ.items()})
    return merged


def _parse_tags(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _read_text_file(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    try:
        p = Path(path)
        if not p.exists():
            return None
        val = p.read_text(encoding="utf-8").strip()
        return val or None
    except Exception:
        return None


def _config_hash_by_sections(sections: Dict[str, Dict[str, str]]) -> str:
    parts: list[str] = []
    for s_name in sorted(sections.keys()):
        fields = sections[s_name]
        for k in sorted(fields.keys()):
            parts.append(f"{s_name}.{k}={fields[k]}\n")
    return sha256("".join(parts).encode("utf-8")).hexdigest()


class Configs(BaseConfigs):
    """
    Configs — фасад конфигурации (TERM-1).

    Источники:
    - configs.env
    - переменные окружения
    - файлы (например CONSUL_HTTP_TOKEN_FILE)
    
    """

    def __init__(self, model: Model, raw_env: Mapping[str, str]) -> None:
        self._model = model
        self._raw_env = dict(raw_env)

    @classmethod
    def load(cls, *, env_file_path: Optional[str] = None) -> "Configs":
        env_path = env_file_path or os.getenv("CONFIGS_ENV_PATH") or "./configs.env"
        file_env = _read_env_file(env_path)
        merged = _merge_env(file_env)

        global_ = GlobalSection(
            domain_root=merged.get("GLOBAL_DOMAIN_ROOT", "terminal.local"),
            version=merged.get("GLOBAL_VERSION", "0.0.0-dev"),
        )

        consul_token = _read_text_file(merged.get("CONSUL_HTTP_TOKEN_FILE"))

        context = ContextSection(
            name=merged.get("SERVICE_NAME", "default-name-service"),
            port=int(merged.get("SERVICE_PORT", "0") or "0"),
            tags=_parse_tags(merged.get("SERVICE_TAGS")),
            consul_token=consul_token,
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
            generate_correlation_if_missing=(merged.get("LOGGING_GENERATE_CORRELATION_IF_MISSING", "true").lower() == "true"),
            correlation_id_len_max=int(merged.get("LOGGING_CORRELATION_ID_LEN_MAX", "64") or "64"),
        )

        metrics = MetricsSection(
            host=merged.get("METRICS_HOST", "0.0.0.0"),
            path=merged.get("METRICS_PATH", "/metrics"),
            port=int(merged.get("METRICS_PORT", "8000") or "8000"),
        )

        fs = FSSection(
            markers_dir=merged.get("FS_MARKERS_DIR", "/fs/terminal/markers"),
            secrets_dir=merged.get("FS_SECRETS_DIR", "/fs/terminal/secrets"),
            certs_dir=merged.get("FS_CERTS_DIR", "/fs/terminal/certs"),
            tmp_dir=merged.get("FS_TMP_DIR", "/fs/terminal/tmp"),
        )

        tls = TLSSection(
            certs_rotate_hours=int(merged.get("TLS_CERTS_ROTATE_HOURS", "168") or "168"),
            reloader_strategy=merged.get("TLS_RELOADER_STRATEGY", "NONE"),
            watch_debounce_ms=int(merged.get("TLS_WATCH_DEBOUNCE_MS", "300") or "300"),
            watch_poll_interval_ms=int(merged.get("TLS_WATCH_POLL_INTERVAL_MS", "500") or "500"),
        )

        kv = KVSection(
            cas_backoff_factor=int(merged.get("KV_CAS_BACKOFF_FACTOR", "2") or "2"),
            cas_max_retries=int(merged.get("KV_CAS_RETRIES", "4") or "4"),
            request_timeout_ms=int(merged.get("KV_REQUEST_TIMEOUT_MS", "3000") or "3000"),
        )

        fsm = FSMSection(
            state_bootstrapping_timeout_ms=int(merged.get("FSM_STATE_BOOTSTRAPPING_TIMEOUT_MS", "5000") or "5000"),
            state_initializing_timeout_ms=int(merged.get("FSM_STATE_INITIALIZING_TIMEOUT_MS", "5000") or "5000"),
            state_securing_timeout_ms=int(merged.get("FSM_STATE_SECURING_TIMEOUT_MS", "10000") or "10000"),
            state_tls_transition_timeout_ms=int(merged.get("FSM_STATE_TLS_TRANSITION_TIMEOUT_MS", "5000") or "5000"),
            state_registering_timeout_ms=int(merged.get("FSM_STATE_REGISTERING_TIMEOUT_MS", "5000") or "5000"),
            state_running_tick_timeout_ms=int(merged.get("FSM_STATE_RUNNING_TICK_TIMEOUT_MS", "1000") or "1000"),
            state_publish_min_interval_ms=int(merged.get("FSM_STATE_PUBLISH_MIN_INTERVAL_MS", "5000") or "5000"),
            degraded_recovery_window_ms=int(merged.get("FSM_DEGRADED_RECOVERY_WINDOW_MS", "60000") or "60000"),
            degraded_transition_window_ms=int(merged.get("FSM_DEGRADED_TRANSITION_WINDOW_MS", "30000") or "30000"),
            degraded_min_duration_ms=int(merged.get("FSM_DEGRADED_MIN_DURATION_MS", "5000") or "5000"),
        )

        registrar = RegistrarSection(
            ttl_sec=int(merged.get("REGISTRAR_TTL_SEC", "15") or "15"),
            heartbeat_period_sec=int(merged.get("REGISTRAR_HEARTBEAT_PERIOD_SEC", "7") or "7"),
            deregister_critical_service_after_sec=int(merged.get("REGISTRAR_DEREGISTER_CRITICAL_SERVICE_AFTER_SEC", "45") or "45"),
            reregistration_cooldown_sec=int(merged.get("REGISTRAR_REREGISTRATION_COOLDOWN_SEC", "15") or "15"),
            max_rereg_attempts_per_window=int(merged.get("REGISTRAR_MAX_REREG_ATTEMPTS_PER_WINDOW", "5") or "5"),
        )

        sections_for_hash: Dict[str, Dict[str, str]] = {
            "global": {"domain_root": global_.domain_root, "version": global_.version},
            "context": {"name": context.name, "port": str(context.port), "tags": ",".join(context.tags)},
            "consul": {"host": consul.host, "http_port": str(consul.http_port), "https_port": str(consul.https_port)},
            "vault": {"host": vault.host, "http_port": str(vault.http_port), "https_port": str(vault.https_port)},
            "traefik": {"host": traefik.host, "http_port": str(traefik.http_port), "https_port": str(traefik.https_port)},
            "logging": {
                "level": logging.level,
                "correlation_id_header": logging.correlation_id_header,
                "generate_correlation_if_missing": str(logging.generate_correlation_if_missing),
                "correlation_id_len_max": str(logging.correlation_id_len_max),
            },
            "metrics": {"host": metrics.host, "port": str(metrics.port), "path": metrics.path},
            "fs": {"markers_dir": fs.markers_dir, "certs_dir": fs.certs_dir, "secrets_dir": fs.secrets_dir, "tmp_dir": fs.tmp_dir},
            "tls": {
                "certs_rotate_hours": str(tls.certs_rotate_hours),
                "reloader_strategy": tls.reloader_strategy,
                "watch_debounce_ms": str(tls.watch_debounce_ms),
                "watch_poll_interval_ms": str(tls.watch_poll_interval_ms),
            },
            "kv": {
                "cas_backoff_factor": str(kv.cas_backoff_factor),
                "cas_max_retries": str(kv.cas_max_retries),
                "request_timeout_ms": str(kv.request_timeout_ms),
            },
            "fsm": {
                "state_bootstrapping_timeout_ms": str(fsm.state_bootstrapping_timeout_ms),
                "state_initializing_timeout_ms": str(fsm.state_initializing_timeout_ms),
                "state_securing_timeout_ms": str(fsm.state_securing_timeout_ms),
                "state_tls_transition_timeout_ms": str(fsm.state_tls_transition_timeout_ms),
                "state_registering_timeout_ms": str(fsm.state_registering_timeout_ms),
                "state_running_tick_timeout_ms": str(fsm.state_running_tick_timeout_ms),
                "state_publish_min_interval_ms": str(fsm.state_publish_min_interval_ms),
                "degraded_recovery_window_ms": str(fsm.degraded_recovery_window_ms),
                "degraded_transition_window_ms": str(fsm.degraded_transition_window_ms),
                "degraded_min_duration_ms": str(fsm.degraded_min_duration_ms),
            },
            "registrar": {
                "ttl_sec": str(registrar.ttl_sec),
                "heartbeat_period_sec": str(registrar.heartbeat_period_sec),
                "deregister_critical_service_after_sec": str(registrar.deregister_critical_service_after_sec),
                "reregistration_cooldown_sec": str(registrar.reregistration_cooldown_sec),
                "max_rereg_attempts_per_window": str(registrar.max_rereg_attempts_per_window),
            },
        }

        config_hash = _config_hash_by_sections(sections_for_hash)

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
            config_hash=config_hash,
        )
        return cls(model=model, raw_env=merged)

    # --- IConfigs ---

    def as_dict(self) -> Mapping[str, Any]:
        # pydantic v2: model_dump()
        return self._model.model_dump()

    def get(self, key: str, default: Any = None) -> Any:
        # простой доступ по raw-env: ключи как в configs.env/ENV
        return self._raw_env.get(key, default)

    @property
    def service_name(self) -> str:
        return self._model.context.name

    # --- extra (удобство для ядра/сервисов) ---

    @property
    def model(self) -> Model:
        return self._model
