# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass

from interfaces import IConfigs


@dataclass(frozen=True)
class Paths:
    markers_dir: str
    certs_dir: str
    secrets_dir: str
    tmp_dir: str

    @classmethod
    def from_cfg(cls, cfg: IConfigs) -> "Paths":
        fs = cfg.fs
        return cls(
            markers_dir=str(fs.markers_dir),
            certs_dir=str(fs.certs_dir),
            secrets_dir=str(fs.secrets_dir),
            tmp_dir=str(fs.tmp_dir),
        )
