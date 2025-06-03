# source\core\base\settings.py


import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


ENV_FILE = Path("/opt/env/.env")
if not ENV_FILE.exists():
    raise FileNotFoundError(f"Environment file not found: {ENV_FILE}")


class EnvSettings(BaseSettings):
    
    ENV_MODE: str = Field(..., description="Environment mode (develop/test/prod)")
    LOG_LEVEL: str = Field("INFO", description="Logging level (e.g. INFO, DEBUG)")

    TRAEFIK_PORT: int = Field(443, description="Traefik UI/API port")

    CONSUL_HOST: str = Field(..., description="Consul agent host")
    CONSUL_PORT: int = Field(..., description="Consul agent port")
    CONSUL_DC: str = Field(..., description="Consul datacenter name")

    VAULT_HOST: str = Field(..., description="Vault server host")
    VAULT_PORT: int = Field(..., description="Vault server port")

    # SERVICE-SPECIFIC
    SERVICE_NAME: str = Field(..., description="This container's logical service name")
    SERVICE_PORT: int = Field(..., description="Internal exposed service port")
    SERVICE_TAGS: str = Field("", description="Optional comma-separated list of tags")
    METRICS_PORT: int = Field(9100, description="Port for Prometheus metrics export")

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"
        # extra = "ignore"


# Singleton instance
settings = EnvSettings()
