from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, Optional

from _base import BaseTLS
from _entities import EventCodeEnum
from _interfaces import IConfigs, IFS, ILogger

from .paths import TlsPaths


class TLS(BaseTLS):
    """
    TLS — фасад TLS (TERM-1).

    Функции:
    - контракт путей сертификатов (TlsPaths)
    - validate_service_chain(name): проверка CA/cert/key
    - fingerprint_bundle(paths): детект изменений набора файлов (для reload)
    
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
        # гарантируем директорию (FS уже должен был сделать layout, но здесь безопасно повторить)
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

    # --- high-level helpers ---

    def validate_service_chain(self, *, name: str) -> bool:
        """
        Минимальная валидация связки CA/cert/key для сервиса `name`.
        Возвращает False при любой проблеме (missing/invalid/mismatch).
        """
        return self.validate_chain(
            ca_file=self._paths.ca(),
            cert_file=self._paths.cert(name),
            key_file=self._paths.key(name),
        )

    def fingerprint_bundle(self, paths: Iterable[Path]) -> str:
        """
        Устойчивый fingerprint набора файлов.
        Используется для детекта "изменились сертификаты" без хранения FSM-стадий.

        Правило:
        - отсутствующий файл учитывается как пустая строка
        - порядок путей не влияет на результат (сортировка по строке)
        """
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
