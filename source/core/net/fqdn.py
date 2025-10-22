from __future__ import annotations
import socket

def normalize_fqdn(host: str) -> str:
    return host.strip()

def reverse_lookup(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ip
