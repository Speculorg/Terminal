# source\core\runtime\tls\sslcontext_reloader.py

from __future__ import annotations
import ssl
from typing import Callable, Optional, Literal

from core.logging import get_logger
from core.runtime.tls.tls_reload import TLSReloader
from core.runtime.tls.utils import build_ssl_context


log = get_logger("tls.reloader.sslcontext")


class SSLContextTLSReloader(TLSReloader):
    """
    TLSReloader для Python-сервисов.
    При получении новой версии перечитывает PEM-файлы и вызывает apply_callback(new_context).
    """

    def __init__(
        self,
        *,
        mode: Literal["server", "client"],
        ca_file: Optional[str],
        cert_file: Optional[str],
        key_file: Optional[str],
        apply_callback: Callable[[ssl.SSLContext], None],
        require_client_cert: bool = False,
        check_hostname: bool = False,
    ) -> None:
        self._mode = mode
        self._ca_file = ca_file
        self._cert_file = cert_file
        self._key_file = key_file
        self._apply = apply_callback
        self._require_client_cert = bool(require_client_cert)
        self._check_hostname = bool(check_hostname)

    def notify_version(self, version: str) -> None:
        """
        Перестраивает ssl.SSLContext из файлов и атомарно подменяет его в сервисе.
        """
        log.info(
            "evt=tls.rebuild_context start version=%s mode=%s", version, self._mode
        )
        ctx = build_ssl_context(
            mode=self._mode,
            ca_file=self._ca_file,
            cert_file=self._cert_file,
            key_file=self._key_file,
            require_client_cert=self._require_client_cert,
            check_hostname=self._check_hostname,
        )
        self._apply(ctx)
        log.info("evt=tls.rebuild_context done version=%s", version)
