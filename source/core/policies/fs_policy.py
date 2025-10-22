from __future__ import annotations
from dataclasses import dataclass

@dataclass
class FSPolicy:
    cfg: object
    logger: object
    metrics: object
    fs: object

    def on_flush(self) -> None:
        """TERM-1: при остановке чистим временный каталог сервиса.
        Без сетевых операций. Без дедлайнов. 
        """
        try:
            tmp_dir = self.fs.paths.tmp_dir
        except Exception:
            # если paths недоступен, ничего не делаем
            return
        try:
            for name in list(self.fs.listdir(tmp_dir)):
                try:
                    self.fs.remove(f"{tmp_dir}/{name}")
                except Exception:
                    # не прерываем остановку сервиса
                    pass
        except Exception:
            pass
