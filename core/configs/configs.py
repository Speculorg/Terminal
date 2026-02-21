from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from core._base import BaseConfigs

from .model import (
    Model,
    GlobalSection,
    ContextSection,
    ConsulSection,
    VaultSection,
    LoggingSection,
    FSSection,
    TLSSection,
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
        # configs.env не должен ломать запуск; ошибки проявятся позже через диагностику/логи
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
    - переменные окружения (docker-compose)
    - файлы (например CONSUL_HTTP_TOKEN_FILE) — читаем содержимое токена в model.context.consul_token
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
        )

        # token content (not path)
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
            http_port=int(merged.get("VAULT_HTTP_PORT", "8200") or "8200"),
            pki_root_path=merged.get("VAULT_PKI_ROOT_PATH", "pki-root"),
            pki_role=merged.get("VAULT_PKI_ROLE", "terminal-leaf"),
        )

        logging = LoggingSection(
            level=merged.get("LOGGING_LEVEL", "INFO"),
        )

        fs = FSSection(
            markers_dir=merged.get("FS_MARKERS_DIR", "/fs/terminal/markers"),
            secrets_dir=merged.get("FS_SECRETS_DIR", "/fs/terminal/secrets"),
            certs_dir=merged.get("FS_CERTS_DIR", "/fs/terminal/certs"),
            tmp_dir=merged.get("FS_TMP_DIR", "/fs/terminal/tmp"),
        )

        tls = TLSSection(
            watch_poll_interval_ms=int(merged.get("TLS_WATCH_POLL_INTERVAL_MS", "500") or "500"),
        )

        fsm = FSMSection(
            state_bootstrapping_timeout_ms=int(merged.get("FSM_STATE_BOOTSTRAPPING_TIMEOUT_MS", "5000") or "5000"),
            state_initializing_timeout_ms=int(merged.get("FSM_STATE_INITIALIZING_TIMEOUT_MS", "5000") or "5000"),
            state_securing_timeout_ms=int(merged.get("FSM_STATE_SECURING_TIMEOUT_MS", "10000") or "10000"),
            state_registering_timeout_ms=int(merged.get("FSM_STATE_REGISTERING_TIMEOUT_MS", "5000") or "5000"),
            state_running_tick_timeout_ms=int(merged.get("FSM_STATE_RUNNING_TICK_TIMEOUT_MS", "1000") or "1000"),
        )

        registrar = RegistrarSection(
            ttl_sec=int(merged.get("REGISTRAR_TTL_SEC", "15") or "15"),
            heartbeat_period_sec=int(merged.get("REGISTRAR_HEARTBEAT_PERIOD_SEC", "7") or "7"),
            deregister_critical_service_after_sec=int(merged.get("REGISTRAR_DEREGISTER_CRITICAL_SERVICE_AFTER_SEC", "45") or "45"),
            reregistration_cooldown_sec=int(merged.get("REGISTRAR_REREGISTRATION_COOLDOWN_SEC", "15") or "15"),
            max_rereg_attempts_per_window=int(merged.get("REGISTRAR_MAX_REREG_ATTEMPTS_PER_WINDOW", "5") or "5"),
        )

        sections_for_hash: Dict[str, Dict[str, str]] = {
            "global": {"domain_root": global_.domain_root},
            "context": {"name": context.name, "port": str(context.port), "tags": ",".join(context.tags)},
            "consul": {"host": consul.host, "http_port": str(consul.http_port), "https_port": str(consul.https_port)},
            "vault": {"http_port": str(vault.http_port), "pki_root_path": vault.pki_root_path, "pki_role": vault.pki_role},
            "logging": {"level": logging.level},
            "fs": {"markers_dir": fs.markers_dir, "certs_dir": fs.certs_dir, "secrets_dir": fs.secrets_dir, "tmp_dir": fs.tmp_dir},
            "tls": {"watch_poll_interval_ms": str(tls.watch_poll_interval_ms)},
            "fsm": {
                "state_bootstrapping_timeout_ms": str(fsm.state_bootstrapping_timeout_ms),
                "state_initializing_timeout_ms": str(fsm.state_initializing_timeout_ms),
                "state_securing_timeout_ms": str(fsm.state_securing_timeout_ms),
                "state_registering_timeout_ms": str(fsm.state_registering_timeout_ms),
                "state_running_tick_timeout_ms": str(fsm.state_running_tick_timeout_ms),
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
            logging=logging,
            fs=fs,
            tls=tls,
            fsm=fsm,
            registrar=registrar,
            config_hash=config_hash,
        )
        return cls(model=model, raw_env=merged)

    # --- IConfigs ---

    def as_dict(self) -> Mapping[str, Any]:
        return self._model.model_dump()