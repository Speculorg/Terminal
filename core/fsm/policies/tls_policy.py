from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from core._base import BasePolicy
from core._entities import ErrorCodeEnum, StateEnum
from core._interfaces import ITLS


@dataclass(frozen=True, slots=True)
class TlsBundle:
    """
    Набор файлов, которые считаются “TLS bundle” для детекта изменений.
    """
    paths: Sequence[Path]


class TlsPolicy(BasePolicy):
    """
    TlsPolicy:
    - SECURING: проверяет связку CA/cert/key (минимальная)
    - RUNNING: детектирует изменение файлов сертификатов (fingerprint bundle)

    Реакция на изменение (event "изменились сертификаты") на этом шаге:
    - policy возвращает RETRY с reason=tls_changed
    - FSM останется в RUNNING и будет повторять (это безопасно)
    
    """

    def __init__(
        self,
        *,
        tls: ITLS,
        ca_file: Path,
        cert_file: Path,
        key_file: Path,
        bundle: Optional[TlsBundle] = None,
    ) -> None:
        super().__init__("TlsPolicy")
        self._tls = tls
        self._ca = ca_file
        self._crt = cert_file
        self._key = key_file

        self._bundle = bundle
        self._last_fp: Optional[str] = None

    def _run_impl(self, *, state: StateEnum):
        if state == StateEnum.SECURING:
            ok = self._tls.validate_chain(ca_file=self._ca, cert_file=self._crt, key_file=self._key)
            if not ok:
                return self.retry(reason="tls_chain_invalid_or_missing", missing=[str(self._ca), str(self._crt), str(self._key)])
            return self.ok(details={"tls_chain_ok": True})

        if state == StateEnum.RUNNING and self._bundle is not None:
            # ITLS не обязан иметь fingerprint_bundle, поэтому используем fingerprint() на каждом файле
            fp = self._bundle_fp(self._bundle.paths)
            if self._last_fp is None:
                self._last_fp = fp
                return self.ok(details={"tls_fp": fp})
            if fp != self._last_fp:
                self._last_fp = fp
                return self.retry(reason="tls_changed", details={"tls_fp": fp})
            return self.ok(details={"tls_fp": fp})

        return self.ok(details={"skip": True})

    def _bundle_fp(self, paths: Iterable[Path]) -> str:
        # Детерминированный fingerprint на стороне policy (не требует расширения ITLS)
        items: list[str] = []
        for p in sorted((Path(x) for x in paths), key=lambda x: str(x)):
            try:
                if not p.exists():
                    items.append(f"{p}:")
                else:
                    items.append(f"{p}:{self._tls.fingerprint(p)}")
            except Exception:
                items.append(f"{p}:")
        import hashlib

        h = hashlib.sha256()
        h.update(("\n".join(items)).encode("utf-8"))
        return h.hexdigest()
