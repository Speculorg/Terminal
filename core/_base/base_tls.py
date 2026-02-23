from __future__ import annotations

import hashlib
import ssl
from pathlib import Path

from core._interfaces import ITLS


class BaseTLS(ITLS):
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
        _ = (name, vault_addr, vault_token_file, pki_path, role, domain_root, ttl, rotate_after_sec)
        return {"rotated": False, "reason": "rotate_not_supported"}