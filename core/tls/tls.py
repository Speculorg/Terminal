from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Iterable, Optional

import requests

from core._base import BaseTLS
from core._entities import EventCodeEnum
from core._interfaces import IConfigs, IFS, ILogger

from .paths import TlsPaths


class TLS(BaseTLS):
    """
    TLS — фасад TLS (TERM-1).

    - контракт путей (TlsPaths)
    - validate_service_chain(name)
    - fingerprint_bundle(paths)
    - rotate_leaf_if_needed(...) через Vault PKI (пер-сервисно)
    """

    def __init__(self, *, fs: IFS, paths: TlsPaths) -> None:
        super().__init__()
        self._fs = fs
        self._paths = paths

    @property
    def paths(self) -> TlsPaths:
        return self._paths

    @classmethod
    def from_configs(cls, *, cfg: IConfigs, fs: IFS, log: Optional[ILogger] = None) -> "TLS":
        certs_dir = Path(str(cfg.get("FS_CERTS_DIR", "/fs/terminal/certs")))
        try:
            fs.ensure_dir(certs_dir)
        except Exception:
            pass

        paths = TlsPaths(certs_dir=certs_dir)

        if log is not None:
            log.event(
                EventCodeEnum.TLS_VALIDATE,
                fields={
                    "certs_dir": str(certs_dir),
                    "ca_file": str(paths.ca()),
                    "contract": "ca.crt + <name>.crt + <name>.key",
                },
            )

        return cls(fs=fs, paths=paths)

    def validate_service_chain(self, *, name: str) -> bool:
        return self.validate_chain(
            ca_file=self._paths.ca(),
            cert_file=self._paths.cert(name),
            key_file=self._paths.key(name),
        )

    def fingerprint_bundle(self, paths: Iterable[Path]) -> str:
        items = []
        for p in sorted((Path(x) for x in paths), key=lambda x: str(x)):
            items.append(f"{p}:{self._safe_file_fp(p)}\n")

        h = hashlib.sha256()
        h.update("".join(items).encode("utf-8"))
        return h.hexdigest()

    def _safe_file_fp(self, path: Path) -> str:
        try:
            if not Path(path).exists():
                return ""
            return self.fingerprint(Path(path))
        except Exception:
            return ""

    # --- rotate via Vault PKI (per-service) ---

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
        svc = str(name).strip()
        if not svc:
            return {"rotated": False, "reason": "empty_name"}

        ca_file = self._paths.ca()
        crt_file = self._paths.cert(svc)
        key_file = self._paths.key(svc)
        pem_file = self._paths.certs_dir / f"{svc}.pem"

        missing: list[str] = []
        if not Path(ca_file).exists():
            missing.append(str(ca_file))
        if not Path(crt_file).exists():
            missing.append(str(crt_file))
        if not Path(key_file).exists():
            missing.append(str(key_file))

        if missing:
            return {"rotated": False, "reason": "missing_files", "missing": missing}

        # not due?
        try:
            now = time.time()
            m = min(Path(crt_file).stat().st_mtime, Path(key_file).stat().st_mtime)
            age = max(0.0, now - m)
            if age < float(max(0, int(rotate_after_sec))):
                return {
                    "rotated": False,
                    "reason": "not_due",
                    "age_sec": round(age, 3),
                    "rotate_after_sec": int(rotate_after_sec),
                }
        except Exception:
            # если не можем прочитать mtime — считаем “нужно ротировать”
            pass

        token = self._read_vault_token(vault_token_file)
        if not token:
            return {"rotated": False, "reason": "vault_token_missing", "token_file": str(vault_token_file)}

        dom = str(domain_root).strip().strip(".") or "terminal.local"
        pki = str(pki_path).strip().strip("/") or "pki-root"
        role2 = str(role).strip() or "terminal-leaf"
        ttl2 = str(ttl).strip() or "10m"

        common_name = f"{svc}.{dom}"
        alt_names = ",".join(self._unique_list([svc, common_name, "localhost"]))
        ip_sans = "127.0.0.1"

        url = f"{str(vault_addr).rstrip('/')}/v1/{pki}/issue/{role2}"
        hdr = {"X-Vault-Token": token}
        payload = {"common_name": common_name, "alt_names": alt_names, "ip_sans": ip_sans, "ttl": ttl2}

        sess = requests.Session()
        r = sess.post(
            url,
            headers=hdr,
            json=payload,
            timeout=(3.0, 15.0),
            verify=str(ca_file),
            cert=(str(crt_file), str(key_file)),
        )
        if r.status_code != 200:
            return {
                "rotated": False,
                "reason": "vault_issue_http",
                "status_code": int(r.status_code),
                "body": (r.text or "")[:256],
            }

        data = r.json() or {}
        data2 = data.get("data") if isinstance(data.get("data"), dict) else {}
        if not isinstance(data2, dict):
            data2 = {}

        cert_pem = str(data2.get("certificate", "") or "").strip()
        key_pem = str(data2.get("private_key", "") or "").strip()
        if not cert_pem or not key_pem:
            return {"rotated": False, "reason": "vault_issue_empty_pem"}

        # atomic replace
        self._fs.write_text_atomic(crt_file, cert_pem + "\n", mode=0o644)
        self._fs.write_text_atomic(key_file, key_pem + "\n", mode=0o600)
        self._fs.write_text_atomic(pem_file, cert_pem + "\n" + key_pem + "\n", mode=0o600)

        return {
            "rotated": True,
            "reason": "issued",
            "name": svc,
            "common_name": common_name,
            "ttl": ttl2,
        }

    def _read_vault_token(self, path: Path) -> str:
        try:
            obj = self._fs.read_json(Path(path))
            v = obj.get("root_token") or obj.get("token") or obj.get("SecretID")
            return str(v or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _unique_list(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in items:
            s = str(x).strip()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out