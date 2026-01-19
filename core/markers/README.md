# core/markers

Markers — фасад маркеров (stage gates), устойчивых файловых “доказательств” выполнения шагов.

## Назначение
- Идемпотентность bootstrap между рестартами контейнера.
- Вычисление `RunMode` (FIRST/NORMAL).
- Простые предикаты готовности (“stage gates”) для FSM.

## Контракт TERM-1
- Директория: `FS_MARKERS_DIR` (default: `/fs/terminal/markers`)
- Суффикс: `MARKERS_SUFFIX` (default: `.done`)
- Маркер: файл `<name><suffix>`.

## Инварианты
- `set()` и `delete()` — идемпотентны.
- Доступ к диску осуществляется через `IFS`.
