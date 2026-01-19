from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TlsPaths:
    """
    Контракт путей TLS в FS_CERTS_DIR.

    Схема:
    - CA: ca.crt
    - leaf cert: <name>.crt
    - leaf key: <name>.key
    """

    certs_dir: Path
    ca_filename: str = "ca.crt"
    cert_ext: str = ".crt"
    key_ext: str = ".key"

    def ca(self) -> Path:
        return self.certs_dir / self.ca_filename

    def cert(self, name: str) -> Path:
        safe = self._safe(name)
        return self.certs_dir / f"{safe}{self.cert_ext}"

    def key(self, name: str) -> Path:
        safe = self._safe(name)
        return self.certs_dir / f"{safe}{self.key_ext}"

    @staticmethod
    def _safe(name: str) -> str:
        # имя сервиса/серта используется в файловой системе
        return name.strip().replace("/", "_").replace("\\", "_")
