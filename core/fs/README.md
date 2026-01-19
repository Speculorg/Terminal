# core/fs

FS — файловый фасад ядра.

## Контракт TERM-1
- root: `/fs/terminal` (или `FS_ROOT`)
- директории:
  - markers: `FS_MARKERS_DIR` (default: `/fs/terminal/markers`)
  - secrets: `FS_SECRETS_DIR` (default: `/fs/terminal/secrets`)
  - certs: `FS_CERTS_DIR` (default: `/fs/terminal/certs`)
  - tmp: `FS_TMP_DIR` (default: `/fs/terminal/tmp`)

## Инварианты
- Запись производится атомарно (`tmp -> os.replace()`), см. `BaseFS`.
- Все операции должны быть идемпотентны и безопасны для повторного запуска контейнера.
