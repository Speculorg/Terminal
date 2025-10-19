from __future__ import annotations
import os
from typing import Callable
from interfaces.i_fs import IFS, IWatcher
from .paths import Paths
from .ops import safe_makedirs, atomic_write, atomic_write_text, atomic_read, atomic_read_text, listdir as _ls, remove as _rm
from .watcher import _Watcher
from .secrets_store import SecretsStore
from .certs_store import CertsStore
from .markers_store import MarkersStore
from .temp_store import TempStore

class FS(IFS):
    def __init__(self, cfg=None) -> None:
        self.paths = Paths()
        # директории из cfg при наличии
        secrets_dir = getattr(getattr(getattr(cfg, "model", None), "fs", None), "secrets_dir", self.paths.secrets_dir)
        certs_dir = getattr(getattr(getattr(cfg, "model", None), "fs", None), "certs_dir", self.paths.certs_dir)
        tmp_dir = self.paths.tmp_dir
        # подфасады
        self.secrets = SecretsStore(secrets_dir)
        self.certs = CertsStore(certs_dir)
        self.markers = MarkersStore(self.paths)
        self.temp = TempStore(tmp_dir)

    # --- базовые IFS ---
    def exists(self, path: str) -> bool:
        return os.path.exists(self.paths.ensure_relative(path))

    def listdir(self, path: str) -> list[str]:
        return _ls(self.paths.ensure_relative(path))

    def remove(self, path: str) -> None:
        _rm(self.paths.ensure_relative(path))

    def makedirs(self, path: str, mode: int = 0o755) -> None:
        safe_makedirs(self.paths.ensure_relative(path), mode=mode)

    def atomic_write(self, path: str, data: bytes, mode: int = 0o644) -> None:
        from .ops import atomic_write as _aw
        _aw(self.paths.ensure_relative(path), data, mode=mode)

    def atomic_write_text(self, path: str, text: str, mode: int = 0o644, encoding: str = "utf-8") -> None:
        from .ops import atomic_write_text as _awt
        _awt(self.paths.ensure_relative(path), text, mode=mode, encoding=encoding)

    def atomic_read(self, path: str) -> bytes:
        from .ops import atomic_read as _ar
        return _ar(self.paths.ensure_relative(path))

    def atomic_read_text(self, path: str, encoding: str = "utf-8") -> str:
        from .ops import atomic_read_text as _art
        return _art(self.paths.ensure_relative(path), encoding=encoding)

    def start_file_watch(self, paths: list[str], on_change: Callable[[list[str]], None], poll_interval_ms: int) -> "IWatcher":
        rels = [self.paths.ensure_relative(p) for p in paths]
        return _Watcher(rels, on_change, poll_interval_ms).start()

# Реэкспорт
SecretsStore = SecretsStore
CertsStore = CertsStore
MarkersStore = MarkersStore
TempStore = TempStore
Paths = Paths
