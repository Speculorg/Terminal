# core/tls

TLS — фасад TLS ядра.

## Контракт TERM-1 (совместимость со старой схемой)
- `FS_CERTS_DIR` (default: `/fs/terminal/certs`)
- CA: `ca.crt`
- leaf cert: `<name>.crt`
- leaf key: `<name>.key`

## Назначение
- Валидация наличия/согласованности CA/cert/key.
- Детект изменений набора файлов сертификатов (fingerprint bundle).

## Не входит в ответственность
- Фасад НЕ генерирует сертификаты (это ответственность Vault/PKI и bootstrap-политик)
- Фасад НЕ делает hot-reload демонов (это ответственность политик/runner)
