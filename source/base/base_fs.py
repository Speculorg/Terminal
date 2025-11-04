from __future__ import annotations
import os
from typing import Callable, Optional, Mapping, Any, List
from interfaces.i_fs import IFS, IWatcher, BytesLike

class BaseFS(IFS):
    """Базовый каркас FS: безопасные операции файловой системы.
    Реализует ensure_layout/safe_list и обёртки атомарных операций.
    Конкретные детали (пути, watcher, хранилища) предоставляет фасад.
    """
    def __init__(self) -> None:
        # Фасад обязан определить: self.paths и методы низкого уровня из ops
        if not hasattr(self, "paths"):
            raise RuntimeError("FS facade must provide self.paths")

    # --- базовые операции ---
    def exists(self, path: str) -> bool:
        return os.path.exists(self.paths.ensure_relative(path))

    def listdir(self, path: str) -> list[str]:
        try:
            return sorted(os.listdir(self.paths.ensure_relative(path)))
        except FileNotFoundError:
            return []

    def safe_list(self, path: str) -> list[str]:
        """Безопасное перечисление только обычных файлов и каталогов. Не кидает исключений."""
        full = self.paths.ensure_relative(path)
        try:
            items = sorted(os.listdir(full))
        except FileNotFoundError:
            return []
        out: list[str] = []
        for name in items:
            p = os.path.join(full, name)
            if os.path.isfile(p) or os.path.isdir(p):
                out.append(name)
        return out

    def remove(self, path: str) -> None:
        try:
            os.remove(self.paths.ensure_relative(path))
        except FileNotFoundError:
            return

    def makedirs(self, path: str, mode: int = 0o755) -> None:
        os.makedirs(self.paths.ensure_relative(path), mode=mode, exist_ok=True)

    # --- атомарные чтение/запись (реализуются через ops.*, предоставляемые фасадом) ---
    def atomic_write(self, path: str, data: BytesLike, mode: int = 0o644) -> None:
        return self._op_atomic_write(self.paths.ensure_relative(path), data, mode=mode)

    def atomic_write_text(self, path: str, text: str, mode: int = 0o644, encoding: str = "utf-8") -> None:
        return self._op_atomic_write_text(self.paths.ensure_relative(path), text, mode=mode, encoding=encoding)

    def atomic_read(self, path: str) -> bytes:
        return self._op_atomic_read(self.paths.ensure_relative(path))

    def atomic_read_text(self, path: str, encoding: str = "utf-8") -> str:
        return self._op_atomic_read_text(self.paths.ensure_relative(path), encoding=encoding)

    # --- layout ---
    def ensure_layout(self) -> None:
        return self._op_ensure_layout(self.paths)

    # --- watcher ---
    def start_file_watch(self, paths: list[str], on_change: Callable[[list[str]], None], poll_interval_ms: int) -> "IWatcher":
        # Фасад обязан предоставить _watcher_start
        rels = [self.paths.ensure_relative(p) for p in paths]
        return self._watcher_start(rels, on_change, poll_interval_ms)
