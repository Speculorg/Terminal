# source\core\kv\certs.py

"""
core.kv.certs
Публикация в KV публичных сертификатов и версий, а также базовое чтение.
"""

from __future__ import annotations
from typing import Dict, Optional, Tuple

from .base import KV
from . import paths
from .utils import now_iso, cas_update_json
from core.logging import get_logger

log = get_logger("kv.certs")


class CertsFacade:
    def __init__(self, kv: KV) -> None:
        self.kv = kv

    # ---- чтение ----

    def get_ca_pem(self) -> Tuple[Optional[str], Optional[int]]:
        return self.kv.get_text(paths.CERTS_CA_PEM)

    def get_service_pem(self, svc: str) -> Tuple[Optional[str], Optional[int]]:
        return self.kv.get_text(paths.certs_svc_pem(svc))

    def get_version(self) -> Tuple[Optional[str], Optional[int]]:
        return self.kv.get_text(paths.CERTS_VERSION)

    # ---- публикация ----

    def publish_ca_pem(self, pem: str) -> bool:
        ok = self.kv.put_text(paths.CERTS_CA_PEM, pem or "")
        if not ok:
            log.error("evt=certs.publish.fail key=%s", paths.CERTS_CA_PEM)
        return ok

    def publish_service_pem(self, svc: str, pem: str) -> bool:
        key = paths.certs_svc_pem(svc)
        ok = self.kv.put_text(key, pem or "")
        if not ok:
            log.error("evt=certs.publish.fail key=%s", key)
        return ok

    def publish_bundle(self, svc_pems: Dict[str, str], *, version: str | int, tries: int = 10) -> bool:
        """
        Публикует набор PEM-ов (cert/<svc>.crt) + обновляет marker vault/certs_status и простую версию.
        """
        # 1) Записываем все PEM-ы
        for svc, pem in svc_pems.items():
            if not self.publish_service_pem(svc, pem):
                return False

        # 2) Обновляем marker JSON (CAS)
        if not self._publish_certs_status_marker(version=version, meta={"services": list(svc_pems.keys())}, tries=tries):
            return False

        # 3) Дублируем простую версию (для лёгких вотчеров, например, Traefik)
        if not self.kv.put_text(paths.CERTS_VERSION, str(version)):
            log.error("evt=certs.version.write.fail key=%s", paths.CERTS_VERSION)
            return False

        return True

    # ---- внутреннее ----

    def _publish_certs_status_marker(self, *, version: str | int, meta: Optional[dict] = None, tries: int = 10) -> bool:
        key = paths.CERTS_STATUS

        def _upd(_: Optional[dict]) -> dict:
            return {
                "version": str(version),
                "updated_at": now_iso(),
                "meta": dict(meta or {}),
            }

        ok = cas_update_json(
            lambda: self.kv.get_json(key),
            lambda obj, cas: self.kv.put_json(key, obj, cas=cas),
            _upd,
            tries=tries,
        )
        if not ok:
            log.error("evt=marker.certs_status.write.fail key=%s", key)
        return ok
