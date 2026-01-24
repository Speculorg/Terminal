# services/vault

Тонкий сервис Vault (TERM-1).

## Режимы
- `vault_http.hcl`: bootstrap-окно (loopback-only в контейнере, TLS выключен)
- `vault_https.hcl`: runtime (TLS включён)

## Bootstrap (TERM-1 минимум)
`config/bootstrap.py` выполняет идемпотентно:
- `sys/init` (1 share / 1 threshold), сохраняет `vault_init.json` в `FS_SECRETS_DIR`
- `sys/unseal`
- включает `pki-root` (по `VAULT_PKI_ROOT_PATH`)
- генерирует root CA и пишет `ca.crt` в `FS_CERTS_DIR`
- выпускает leaf cert/key для `vault` и `consul` и пишет:
  - `vault.crt`, `vault.key`
  - `consul.crt`, `consul.key`
- выставляет маркеры:
  - `vault_init.done`
  - `vault_initial_pem.done`

## Примечания
- В TERM-1 ключи unseal и root token хранятся в `FS_SECRETS_DIR` (локальный threat model).
- Строгий mTLS на listener Vault включим вместе с Traefik (когда будет кто-то, кто способен ходить в Vault по client cert).
