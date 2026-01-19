# core/registrar

Registrar — фасад service discovery / registry.

## TERM-1
- Реализация: Consul Agent HTTP API
- Регистрация: `/v1/agent/service/register`
- Heartbeat (TTL): `/v1/agent/check/pass/<check_id>`
- Deregister: `/v1/agent/service/deregister/<service_id>`

## Токен
- основной источник: `cfg.model.context.consul_token` (если Configs его заполнил из CONSUL_HTTP_TOKEN_FILE)
- fallback: `CONSUL_HTTP_TOKEN`

## Примечания
- На этом шаге регистратор работает по HTTP/HTTPS в зависимости от `CONSUL_SCHEME`.
- Политики FSM отвечают за “bootstrap-окно” и переключение режимов, а не этот пакет.
