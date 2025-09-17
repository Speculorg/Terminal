# source\core\runtime\tls\client_reloader.py

from __future__ import annotations

import ssl
from pathlib import Path
from typing import Optional

from core.runtime.tls.tls_reload import TLSReloader
from core.logging import get_logger

log = get_logger("tls.client_reloader")


class ClientTLSReloader(TLSReloader):
    """
    Релоадер клиентского SSLContext.
    - Хранит пути к CA, client cert/key.
    - При notify_version(version) пересоздаёт SSLContext (горячая подмена).
    - Потокобезопасность не усложняем: пересоздание контекста атомарно и быстро.
    """

    def __init__(
        self,
        *,
        ca_file: str | Path,
        cert_file: Optional[str | Path] = None,
        key_file: Optional[str | Path] = None,
        check_hostname: bool = True,
        require_cert: bool = True,
    ) -> None:
        self._ca = Path(ca_file)
        self._crt = Path(cert_file) if cert_file else None
        self._key = Path(key_file) if key_file else None
        self._check_hostname = bool(check_hostname)
        self._require_cert = bool(require_cert)

        self._sslctx: ssl.SSLContext = self._make_context()

    def _make_context(self) -> ssl.SSLContext:
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        if self._ca.exists():
            ctx.load_verify_locations(cafile=str(self._ca))
        else:
            log.warning("evt=tls.client.ca.missing path=%s", self._ca)

        if self._crt and self._crt.exists():
            if self._key and self._key.exists():
                ctx.load_cert_chain(certfile=str(self._crt), keyfile=str(self._key))
            else:
                # допустимо, если key встроен в cert или не требуется
                ctx.load_cert_chain(certfile=str(self._crt))

        ctx.verify_mode = ssl.CERT_REQUIRED if self._require_cert else ssl.CERT_NONE
        ctx.check_hostname = self._check_hostname
        return ctx

    # --- TLSReloader API ---
    def notify_version(self, version: str) -> None:  # noqa: D401
        """
        Получили новую версию бандла - пересоздаём SSLContext.
        """
        try:
            self._sslctx = self._make_context()
            log.info("evt=tls.client.ctx.reloaded version=%s", version)
        except Exception as exc:  # noqa: BLE001
            log.warning("evt=tls.client.ctx.reload.fail err=%s", exc)

    # --- Consumer API ---
    @property
    def ssl_context(self) -> ssl.SSLContext:
        return self._sslctx
