# source\core\base\settings.py

"""
Speculorg.Terminal - Centralized Environment Settings

Loads validated environment variables from mounted file (/opt/env/.env),
ready for Vault and Consul integration.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


ENV_FILE = Path("/opt/env/.env")
if not ENV_FILE.exists():
    raise FileNotFoundError(f"Environment file not found: {ENV_FILE}")


class EnvSettings(BaseSettings):
    # 🌐 GLOBAL
    ENV_MODE: str = Field(..., description="Environment mode (develop/test/prod)")
    LOG_LEVEL: str = Field("INFO", description="Logging level (e.g. INFO, DEBUG)")
    PYTHONUNBUFFERED: int = Field(1, description="Unbuffered stdout")

    # 🧭 CONSUL
    CONSUL_HOST: str = Field(..., description="Consul agent host")
    CONSUL_PORT: int = Field(..., description="Consul agent port")
    CONSUL_DC: str = Field(..., description="Consul datacenter name")
    CONSUL_TIMEOUT: int = Field(..., description="Consul connection timeout (seconds)")
    CONSUL_CHECK_INTERVAL: str = Field(..., description="Consul service check interval")
    CONSUL_CHECK_TIMEOUT: str = Field(..., description="Consul service check timeout")

    # 🔐 VAULT
    VAULT_ADDR: str = Field(..., description="Vault server address")
    # VAULT_DEV_ROOT_TOKEN_ID: str = Field(..., description="Vault dev root token")
    # VAULT_DEV_LISTEN_ADDRESS: str = Field(..., description="Vault listen address")

    # 🧊 TRAEFIK
    TRAEFIK_PORT: int = Field(..., description="Traefik UI/API port")

    # 🛢 POSTGRES
    POSTGRES_USER: str = Field(..., description="PostgreSQL username")
    POSTGRES_PASSWORD: str = Field(..., description="PostgreSQL password")
    POSTGRES_DB: str = Field(..., description="PostgreSQL database name")
    POSTGRES_PORT: int = Field(..., description="PostgreSQL port")

    # 🧠 REDIS
    REDIS_PORT: int = Field(..., description="Redis port")

    # 📦 RABBITMQ
    RABBITMQ_DEFAULT_USER: str = Field(..., description="RabbitMQ username")
    RABBITMQ_DEFAULT_PASS: str = Field(..., description="RabbitMQ password")
    RABBITMQ_PORT: int = Field(..., description="RabbitMQ port")
    RABBITMQ_MANAGEMENT_PORT: int = Field(..., description="RabbitMQ web UI port")

    # 🔑 KEYCLOAK
    KEYCLOAK_ADMIN: str = Field(..., description="Keycloak admin username")
    KEYCLOAK_ADMIN_PASSWORD: str = Field(..., description="Keycloak admin password")
    KEYCLOAK_PORT: int = Field(..., description="Keycloak HTTP port")
    KEYCLOAK_REALM: str = Field(..., description="Keycloak realm name")
    KEYCLOAK_CLIENT_ID: str = Field(..., description="Keycloak service client ID")
    KEYCLOAK_CLIENT_SECRET: str = Field(..., description="Keycloak service client secret")

    # ⚙️ SERVICE-SPECIFIC
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
