from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ITLS(Protocol):
    """
    Порт TLS: контракт PEM и минимальные операции TLS.
    """

    def validate_chain(self, *, ca_file: Path, cert_file: Path, key_file: Path) -> bool:
        ...

    def fingerprint(self, path: Path) -> str:
        ...

    def rotate_leaf_if_needed(
        self,
        *,
        name: str,
        vault_addr: str,
        vault_token_file: Path,
        pki_path: str,
        role: str,
        domain_root: str,
        ttl: str,
        rotate_after_sec: int,
    ) -> dict[str, object]:
        """
        Пер-сервисная ротация leaf сертификата.

        Правило:
        - если cert/key отсутствуют → rotated=False + reason=missing_files
        - если возраст (mtime) cert/key >= rotate_after_sec → перевыпуск через Vault PKI
        - иначе → rotated=False + reason=not_due
        """
        ...