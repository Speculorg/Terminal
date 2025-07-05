# source\core\base\settings.py


from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


ENV_FILE = Path("/opt/env/.env")


class EnvSettings(BaseSettings):
    ENV_MODE: str = Field("develop", description="Execution mode: develop / test / prod")
    LOG_LEVEL: str = Field("INFO", description="Root logging level")

    CONSUL_HOST: str = Field("consul", description="Consul agent host")
    CONSUL_PORT: int = Field(8500, description="Consul HTTP port")
    CONSUL_DC:   str = Field("speculorg-dc", description="Consul datacenter")

    VAULT_HOST: str = Field("vault", description="Vault host")
    VAULT_PORT: int = Field(8200, description="Vault HTTP port")

    TRAEFIK_PORT: int = Field(443, description="Traefik HTTPS entry-point")

    SERVICE_NAME: str = Field(..., description="Logical name of the containerised service")
    SERVICE_PORT: int = Field(..., description="Internal port the service listens on")
    SERVICE_TAGS: str = Field("",   description="Comma-separated list of Consul tags")

    CONSUL_HTTP_TOKEN_FILE: str = Field("", description="Path to Consul ACL token for the running service")


    class Config:
        env_file = ENV_FILE
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = EnvSettings()
