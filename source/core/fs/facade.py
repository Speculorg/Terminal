from __future__ import annotations
from typing import Callable
from interfaces.i_fs import IFS, IWatcher
from interfaces import IConfigs
from base.base_fs import BaseFS
from .paths import Paths
from .ops import ensure_layout as _ensure_layout
from .ops import atomic_write as _aw, atomic_write_text as _awt, atomic_read as _ar, atomic_read_text as _art
from .watcher import _Watcher
from .secrets_store import SecretsStore
from .certs_store import CertsStore
from .markers_store import MarkersStore
from .temp_store import TempStore

class FS(BaseFS):
    def __init__(self, cfg: IConfigs) -> None:
        # Инициализируем пути фасада ДО вызова BaseFS.__init__
        self.paths  = Paths(
            markers_dir =str(cfg.fs.markers_dir),
            secrets_dir =str(cfg.fs.secrets_dir),
            certs_dir   =str(cfg.fs.certs_dir),
            tmp_dir     =str(cfg.fs.tmp_dir),
        )
        # Внутренние сторы
        self.markers    = MarkersStore(self.paths.markers_dir)
        self.secrets    = SecretsStore(self.paths.secrets_dir)
        self.certs      = CertsStore(self.paths.certs_dir)
        self.temp       = TempStore(self.paths.tmp_dir)
        super().__init__()

    # --- низкоуровневые операции, которые использует BaseFS ---
    def _op_ensure_layout(self, paths: Paths) -> None:
        _ensure_layout(paths)

    def _op_atomic_write(self, abs_path: str, data, *, mode: int = 0o644) -> None:
        _aw(abs_path, data, mode=mode)

    def _op_atomic_write_text(self, abs_path: str, text: str, *, mode: int = 0o644, encoding: str = "utf-8") -> None:
        _awt(abs_path, text, mode=mode, encoding=encoding)

    def _op_atomic_read(self, abs_path: str) -> bytes:
        return _ar(abs_path)

    def _op_atomic_read_text(self, abs_path: str, *, encoding: str = "utf-8") -> str:
        return _art(abs_path, encoding=encoding)

    def _watcher_start(self, abs_paths: list[str], on_change: Callable[[list[str]], None], poll_interval_ms: int) -> "IWatcher":
        return _Watcher(abs_paths, on_change, poll_interval_ms).start()
