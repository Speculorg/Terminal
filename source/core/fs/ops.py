from __future__ import annotations
import os, tempfile

def safe_makedirs(path: str, mode: int = 0o755) -> None:
    os.makedirs(path, mode=mode, exist_ok=True)

def atomic_write(path: str, data: bytes, mode: int = 0o644) -> None:
    d = os.path.dirname(path) or "."
    safe_makedirs(d, 0o755)
    fd, tmp_path = tempfile.mkstemp(dir=d)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

def atomic_write_text(path: str, text: str, mode: int = 0o644, encoding: str = "utf-8") -> None:
    atomic_write(path, text.encode(encoding), mode=mode)

def atomic_read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def atomic_read_text(path: str, encoding: str = "utf-8") -> str:
    return atomic_read(path).decode(encoding)

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
