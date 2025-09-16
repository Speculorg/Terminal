# source\core\net\__init__.py

"""
Агрегат core.net
Единая точка входа для сетевых утилит ядра:
- fqdn(name, domain_root) -> str
- build_url(host, port_http, port_https, path="", tls=False) -> str
"""

from .url import fqdn, build_url

__all__ = ["fqdn", "build_url"]
