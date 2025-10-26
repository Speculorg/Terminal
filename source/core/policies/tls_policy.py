from __future__ import annotations
from typing import Set

from entities import StateEnum


class TLSPolicy:
    @staticmethod
    def _has_mode(run_profile, mode: str) -> bool:
        start_cmd = getattr(run_profile, "start_cmd", None) or {}
        return mode in start_cmd

    @staticmethod
    def _securing_gates(run_profile) -> Set[str]:
        gates = getattr(run_profile, "stage_gates", {}) or {}
        return set(gates.get(StateEnum.SECURING, set()))

    @staticmethod
    def decide_initial_mode(markers, run_profile) -> str:
        has_http = TLSPolicy._has_mode(run_profile, "http")
        has_https = TLSPolicy._has_mode(run_profile, "https")
        if has_https and not has_http:
            return "https"
        if has_http and not has_https:
            return "http"
        required = TLSPolicy._securing_gates(run_profile)
        if not required:
            return "http"
        try:
            ok = all(getattr(markers, "exists")(m) for m in required)
        except Exception:
            ok = False
        return "https" if ok else "http"
