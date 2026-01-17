from __future__ import annotations
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ITLS(Protocol):
    """
    Порт TLS: загрузка/валидация файлового контракта PEM.
    """

    def validate_chain(self, *, ca_file: Path, cert_file: Path, key_file: Path) -> bool:
        """Проверка согласованности CA/cert/key (минимальная, без онлайн-OCSP)."""
        ...

    def fingerprint(self, path: Path) -> str:
        """Стабильный fingerprint содержимого файла (для детекта изменений)."""
        ...
