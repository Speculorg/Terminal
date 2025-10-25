# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass

# Внимание: никаких хардкодов путей. Всё берём из Configs.fs.*

@dataclass(frozen=True)
class Paths:
    markers_dir: str
    certs_dir: str
    secrets_dir: str
    tmp_dir: str

    @classmethod
    def from_cfg(cls, cfg) -> "Paths":
        fs = cfg.fs
        return cls(
            markers_dir=fs.markers_dir,
            certs_dir=fs.certs_dir,
            secrets_dir=fs.secrets_dir,
            tmp_dir=fs.tmp_dir,
        )

    # Маркерный файл (плоское имя: <svc>_<name>.done)
    def marker_file(self, name: str) -> str:
        return f"{self.markers_dir}/{name}"

    # Секрет
    def secret_file(self, name: str) -> str:
        return f"{self.secrets_dir}/{name}"

    # Временный файл
    def tmp_file(self, name: str) -> str:
        return f"{self.tmp_dir}/{name}"

    # Типовые PEM пути
    @property
    def pem_privkey(self) -> str:
        return f"{self.certs_dir}/privkey.pem"

    @property
    def pem_cert(self) -> str:
        return f"{self.certs_dir}/cert.pem"

    @property
    def pem_fullchain(self) -> str:
        return f"{self.certs_dir}/fullchain.pem"

    @property
    def pem_ca(self) -> str:
        return f"{self.certs_dir}/ca.crt"