# source/core/utils/fs.py

from __future__ import annotations
from typing import Optional


def read_first_line(path: str) -> Optional[str]:
    """
    Безопасно читает первую строку файла и обрезает пробелы.
    Возвращает None при любой ошибке (файл отсутствует, нет доступа и т.д.).
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return (f.readline() or "").strip()
    except Exception:
        return None
