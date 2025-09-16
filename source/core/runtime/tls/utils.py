# source\core\runtime\tls\utils.py

from __future__ import annotations
import os
import ssl
from typing import Optional, Literal

from core.logging import get_logger


log = get_logger("tls.utils")


def _safe_read_first_line(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return (f.readline() or "").strip()


def read_text(path: str) -> str:
    """
    Безопасно читает текстовый файл целиком (PEM).
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def exists(path: Optional[str]) -> bool:
    return bool(path) and os.path.exists(str(path))


def build_ssl_context(
    *,
    mode: Literal["server", "client"],
    ca_file: Optional[str] = None,
    cert_file: Optional[str] = None,
    key_file: Optional[str] = None,
    require_client_cert: bool = False,
    check_hostname: bool = False,
) -> ssl.SSLContext:
    """
    Строит ssl.SSLContext из PEM-файлов.

    mode="server"  -> контекст серверной стороны;
    mode="client"  -> контекст клиентской стороны.

    require_client_cert=True  -> запрашивать и проверять клиентский сертификат (mTLS).
    check_hostname=True       -> проверка имени (обычно только для client).
    """
    if mode == "server":
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    else:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    # CA
    if exists(ca_file):
        ctx.load_verify_locations(cafile=ca_file)
    else:
        # Подхватываем системные корни (на случай отсутствия кастомного CA)
        try:
            ctx.load_default_certs()
        except Exception as exc:  # noqa: BLE001
            log.warning("evt=tls.ca.load_default_certs.fail err=%s", exc)

    # Сертификат/ключ
    if exists(cert_file) and exists(key_file):
        ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)

    # Политики верификации
    if mode == "server":
        if require_client_cert:
            ctx.verify_mode = ssl.CERT_REQUIRED
        else:
            ctx.verify_mode = ssl.CERT_NONE
        # минимальная версия TLS 1.2
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    else:  # client
        ctx.check_hostname = bool(check_hostname)
        ctx.verify_mode = ssl.CERT_REQUIRED if exists(ca_file) else ssl.CERT_NONE
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    return ctx
