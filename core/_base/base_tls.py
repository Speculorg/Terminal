from __future__ import annotations
import hashlib
import ssl
from pathlib import Path

from core._interfaces import ITLS


class BaseTLS(ITLS):
    """
    Базовый TLS фасад: fingerprint + минимальная валидация связки CA/cert/key.

    validate_chain():
    - проверяет, что файлы существуют
    - проверяет, что key подходит к cert (через SSLContext.load_cert_chain)
    - проверяет, что CA файл может быть загружен в verify store
    Это не "полная PKI-валидация", но достаточный базовый инвариант для TERM-1.
    """

    def validate_chain(self, *, ca_file: Path, cert_file: Path, key_file: Path) -> bool:
        ca = Path(ca_file)
        crt = Path(cert_file)
        key = Path(key_file)

        if not (ca.exists() and crt.exists() and key.exists()):
            return False

        try:
            ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
            ctx.load_verify_locations(cafile=str(ca))
            ctx.load_cert_chain(certfile=str(crt), keyfile=str(key))
            return True
        except Exception:
            return False

    def fingerprint(self, path: Path) -> str:
        p = Path(path)
        h = hashlib.sha256()
        h.update(p.read_bytes())
        return h.hexdigest()
