# services/vault/config/vault_http.hcl
# Bootstrap-режим: Vault слушает только loopback внутри контейнера.

disable_mlock = true
ui = true

storage "consul" {
  address = "consul:8500"
  path = "vault/"
}

listener "tcp" {
  address     = "127.0.0.1:8200"
  tls_disable = 1
}

# В bootstrap-режиме адреса можно держать loopback.
api_addr     = "http://127.0.0.1:8200"
cluster_addr = "http://127.0.0.1:8201"
