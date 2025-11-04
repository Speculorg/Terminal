from __future__ import annotations
import os, tempfile, io
from typing import Iterable

def safe_makedirs(path: str, mode: int = 0o755) -> None:
    os.makedirs(path, mode=mode, exist_ok=True)

def ensure_layout(paths) -> None:
    """Создаёт каталоги fs/terminal/*, если их ещё нет.
    Пытается создать совместимый симлинк /certs -> paths.certs_dir.
    Ошибки на создание симлинка в / игнорируются.
    """
    safe_makedirs(paths.markers_dir, 0o755)
    safe_makedirs(paths.secrets_dir, 0o700)
    safe_makedirs(paths.certs_dir,   0o750)
    safe_makedirs(paths.tmp_dir,     0o700)
    try:
        if os.path.islink('/certs') or os.path.exists('/certs'):
            return
        os.symlink(paths.certs_dir, '/certs')
    except Exception:
        pass

def listdir(path: str) -> list[str]:
    try:
        return sorted(os.listdir(path))
    except FileNotFoundError:
        return []

def remove(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        return

# --- атомарные операции ---
def _atomic_replace(target: str, tmp_path: str, mode: int) -> None:
    os.chmod(tmp_path, mode)
    os.replace(tmp_path, target)

def atomic_write(path: str, data: bytes | bytearray | memoryview, mode: int = 0o644) -> None:
    d = os.path.dirname(path) or '.'
    safe_makedirs(d, 0o755)
    fd, tmp = tempfile.mkstemp(prefix='.aw_', dir=d)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(memoryview(data))
        _atomic_replace(path, tmp, mode)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

def atomic_write_text(path: str, text: str, mode: int = 0o644, encoding: str = 'utf-8') -> None:
    atomic_write(path, text.encode(encoding), mode=mode)

def atomic_read(path: str) -> bytes:
    with open(path, 'rb') as f:
        return f.read()

def atomic_read_text(path: str, encoding: str = 'utf-8') -> str:
    return atomic_read(path).decode(encoding)
