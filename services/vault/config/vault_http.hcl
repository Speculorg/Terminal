# services/vault/config/vault_http.hcl
# Bootstrap-режим: HTTP (без TLS) — только на bootstrap-окно.
# В TERM-1 нам нужно, чтобы другие контейнеры могли достучаться до Vault на старте (init/unseal),
# поэтому слушаем на 0.0.0.0 (а не loopback).

disable_mlock = true
ui = true

storage "consul" {
  address = "consul:8500"
  path = "vault/"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
}

api_addr     = "http://vault:8200"
cluster_addr = "http://vault:8201"
