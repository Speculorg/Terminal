# core/fsm/policies

Набор политик TERM-1 для FSM.

## Принципы
- Политика возвращает только `OK/RETRY/FAIL`.
- Политики должны быть тонкими и идемпотентными.
- Запрещено “внутреннее состояние” политики, влияющее на корректность (кроме кэша fingerprint).

## Политики

- `MarkerPolicy`
  - проверяет наличие stage-gates (маркеры) на текущем состоянии.
- `NetPolicy`
  - выполняет TCP/HTTP checks, блокирует переход пока недоступно.
- `BootstrapPolicy`
  - обёртка для bootstrap-функции сервиса, выставляет done-маркеры.
- `TlsPolicy`
  - валидация CA/cert/key; детект изменения TLS bundle (fingerprint).
- `DaemonPolicy`
  - управление демоном (http/https режимы, живость, останов).
- `RegistrarPolicy`
  - регистрация в Consul и TTL heartbeat.

## Ограничения TERM-1
- Полный bootstrap (ACL/init/unseal/PKI) реализуется кодом сервиса и вызывается из BootstrapPolicy.
- Детект “certs changed” не делает reload сам по себе; это добавляется отдельной политикой или расширением DaemonPolicy.
