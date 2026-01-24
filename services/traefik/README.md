# services/traefik

Тонкий сервис Traefik (TERM-1).

## Схема
- Запуск через ядро: `BaseService -> Deps -> FSM -> Policies -> DaemonRunner`
- HTTP bootstrap-окно: Traefik слушает только loopback (`127.0.0.1:8080`) по `traefik_http.yml`
- HTTPS runtime: Traefik слушает `:443` по `traefik_https.yml`

## Конфиги
- `config/traefik_http.yml` — минимальный старт процесса (loopback-only)
- `config/traefik_https.yml` — runtime конфиг, providers: file + consulCatalog
- `config/dynamic.yml` — TLS options для mTLS на входе

## Gate-маркеры (TERM-1)
Traefik переходит в SECURING/HTTPS только после:
- `vault_init.done`
- `vault_initial_pem.done`
- `consul_tokens.done`

## Примечания
- В этом шаге мы ограничиваемся корректным запуском Traefik под управлением ядра.
- Конфигурация ConsulCatalog (token/CA) и outgoing mTLS (serversTransport) доводятся отдельным шагом,
  чтобы не смешивать “сборку пакета сервиса” с “тонкой интеграцией”.
