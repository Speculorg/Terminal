# source\core\kv\certs.py

"""
core.kv.certs
Публикация в KV публичных сертификатов и версий.
"""

from __future__ import annotations
from typing import Dict, Optional

from .base import KV
from . import paths
from .utils import now_iso
from core.logging import get_logger

log = get_logger("kv.certs")


class CertsFacade:
    def __init__(self, kv: KV) -> None:
        self.kv = kv

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
        if not self.kv.marker.publish_certs_status(version=version, meta={"services": list(svc_pems.keys())}, tries=tries):
            return False

        # 3) Дублируем простую версию (для Traefik)
        if not self.kv.put_text(paths.CERTS_VERSION, str(version)):
            log.error("evt=certs.version.write.fail key=%s", paths.CERTS_VERSION)
            return False

        return True
