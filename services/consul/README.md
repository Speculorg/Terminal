# services/consul

Тонкий сервис Consul (TERM-1).

## Назначение
- Запускает Consul через ядро: `BaseService → DepsFactory → FSM`.
- Bootstrap выполняется автоматически без ручных шагов при `docker compose up`.

## Режимы
- **HTTP bootstrap-окно**: Consul слушает `127.0.0.1:8500` внутри контейнера (`consul_http.hcl`).
- **HTTPS runtime**: Consul слушает `0.0.0.0:8501` (`consul_https.hcl`), mTLS включён.

## Bootstrap
`configs/bootstrap.py`:
- ждёт доступность `GET /v1/status/leader` на loopback HTTP;
- выполняет `PUT /v1/acl/bootstrap`;
- сохраняет токен в `FS_SECRETS_DIR/consul_acl_bootstrap_token.json`;
- выставляет маркеры `consul_bootstrap.done`, `consul_tokens.done`.

## RunProfile
Сервис задаёт только:
- `stage_gates` (ожидание внешних маркеров, например от Vault PKI)
- `start_cmd` (http/https)

Остальная логика находится в ядре.
