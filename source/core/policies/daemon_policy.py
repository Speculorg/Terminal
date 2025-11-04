from __future__ import annotations
from typing import List


class DaemonPolicy:
    """Строит финальную команду старта демона на основе профиля и выбранного режима."""
    @staticmethod
    def build_start_cmd(run_profile, mode: str) -> List[str]:
        start_cmd = getattr(run_profile, "start_cmd", None) or {}
        if mode not in start_cmd:
            raise ValueError(f"start_cmd for mode '{mode}' not defined")
        cmd = start_cmd[mode]
        if not isinstance(cmd, (list, tuple)) or not cmd:
            raise ValueError("start_cmd must be a non-empty list[str]")
        return list(cmd)


    @staticmethod
    def resolve_port(cfg, run_profile, mode: str) -> int:
        name = getattr(cfg.context, "name", None)
        try:
            if name == "consul":
                return int(cfg.consul.http_port if mode == "http" else cfg.consul.https_port)
            if name == "vault":
                return int(cfg.vault.http_port if mode == "http" else cfg.vault.https_port)
            if name == "traefik":
                return int(cfg.context.port)
            return int(cfg.context.port)
        except Exception:
            return int(cfg.context.port)
