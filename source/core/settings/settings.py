# source\core\settings\settings.py


"""
Speculorg.Terminal settings
- Данные конфигурации и их загрузка.
"""

from __future__ import annotations
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple


CONFIG_DIR = Path(os.getenv("SERVICE_CONFIG_DIR", "/opt/config"))
GLOBAL_CFG = CONFIG_DIR / "settings.env"

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _load_kv(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    
    data: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        # убираем инлайн-комментарий, если значение не в кавычках
        if not (v.startswith('"') or v.startswith("'")):
            pos = v.find(" #")
            if pos != -1:
                v = v[:pos].rstrip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        data[k] = v
    return data


def _get(map_: Dict[str, str], key: str, default: str) -> str:
    return os.environ.get(key, map_.get(key, default))


def _as_bool(v: str, default: bool = False) -> bool:
    s = str(v).strip().lower()
    return True if s in _TRUE else False if s in _FALSE else bool(default)


def _as_int(v: str, default: int, lo: int = 0, hi: int = 65535) -> int:
    try:
        x = int(str(v).strip())
        if x < lo or x > hi:
            return default
        return x
    except Exception:
        return default


def _as_float(v: str, default: float, lo: float = 0.0) -> float:
    try:
        x = float(str(v).strip())
        return x if x >= lo else default
    except Exception:
        return default


def _as_list(v: str) -> Tuple[str, ...]:
    if not v:
        return tuple()
    return tuple(s.strip() for s in v.replace(";", ",").split(",") if s.strip())


def _as_path(v: str, default: str) -> Path:
    return Path(v) if v else Path(default)


def _as_duration(v: str, default_seconds: float) -> float:
    """
    Парсит "500ms" | "30s" | "5m" | "1h" в секунды (float).
    Если строка — число, трактуем как секунды.
    """
    s = str(v).strip().lower()
    m = re.match(r"^(\d+(?:\.\d+)?)(ms|s|m|h)$", s)
    if not m:
        try:
            return float(s)
        except Exception:
            return default_seconds
    val, unit = float(m.group(1)), m.group(2)
    return val / 1000 if unit == "ms" else val if unit == "s" else val * 60 if unit == "m" else val * 3600



@dataclass(frozen=True, slots=True)
class Settings:
    # DOMAIN / NAMESPACES
    DOMAIN_ROOT: str

    # LOGGING
    LOG_LEVEL: str

    # DIRECTORIES
    DIR_CERTS: Path
    DIR_SECRETS: Path

    # CONSUL
    CONSUL_HOST: str
    CONSUL_PORT_HTTP: int
    CONSUL_PORT_HTTPS: int
    CONSUL_DC: str

    # VAULT
    VAULT_HOST: str
    VAULT_PORT_HTTP: int
    VAULT_PORT_HTTPS: int  # обычно тот же 8200, оставлен для единообразия

    # TRAEFIK
    TRAEFIK_HOST: str
    TRAEFIK_PORT_HTTP: int
    TRAEFIK_PORT_HTTPS: int

    # SERVICE (задаётся через docker-compose: environment)
    SERVICE_NAME: str
    SERVICE_PORT: int
    SERVICE_TAGS: Tuple[str, ...]
    SERVICE_CONFIG_DIR: str
    SERVICE_HEALTH_FILE: str
    CONSUL_HTTP_TOKEN_FILE: str

    @staticmethod
    def load() -> "Settings":
        file_map = _load_kv(GLOBAL_CFG)

        return Settings(
            # DOMAIN
            DOMAIN_ROOT=_get(file_map, "DOMAIN_ROOT", "terminal.speculorg.localhost").strip() or "terminal.speculorg.localhost",

            # LOGGING
            LOG_LEVEL=_get(file_map, "LOG_LEVEL", "INFO"),

            # DIRS
            DIR_CERTS=_as_path(_get(file_map, "DIR_CERTS", "/certs"), "/certs"),
            DIR_SECRETS=_as_path(_get(file_map, "DIR_SECRETS", "/secrets"), "/secrets"),

            # CONSUL
            CONSUL_HOST=_get(file_map, "CONSUL_HOST", "consul"),
            CONSUL_PORT_HTTP=_as_int(_get(file_map, "CONSUL_PORT_HTTP", "8500"), 8500, 1, 65535),
            CONSUL_PORT_HTTPS=_as_int(_get(file_map, "CONSUL_PORT_HTTPS", "8501"), 8501, 1, 65535),
            CONSUL_DC=_get(file_map, "CONSUL_DC", "speculorg-dc"),

            # VAULT
            VAULT_HOST=_get(file_map, "VAULT_HOST", "vault"),
            VAULT_PORT_HTTP=_as_int(_get(file_map, "VAULT_PORT_HTTP", "8200"), 8200, 1, 65535),
            VAULT_PORT_HTTPS=_as_int(_get(file_map, "VAULT_PORT_HTTPS", "8200"), 8200, 1, 65535),

            # TRAEFIK
            TRAEFIK_HOST=_get(file_map, "TRAEFIK_HOST", "traefik"),
            TRAEFIK_PORT_HTTP=_as_int(_get(file_map, "TRAEFIK_PORT_HTTP", "80"), 80, 1, 65535),
            TRAEFIK_PORT_HTTPS=_as_int(_get(file_map, "TRAEFIK_PORT_HTTPS", "443"), 443, 1, 65535),

            # SERVICE (compose environment)
            SERVICE_NAME=os.getenv("SERVICE_NAME", ""),
            SERVICE_PORT=_as_int(os.getenv("SERVICE_PORT", "0"), 0, 0, 65535),
            SERVICE_TAGS=_as_list(os.getenv("SERVICE_TAGS", "")),
            SERVICE_CONFIG_DIR=os.getenv("SERVICE_CONFIG_DIR", "/opt/config"),
            SERVICE_HEALTH_FILE=os.getenv("SERVICE_HEALTH_FILE", "no_health_file"),
            CONSUL_HTTP_TOKEN_FILE=os.getenv("CONSUL_HTTP_TOKEN_FILE", ""),
        )


settings = Settings.load()
