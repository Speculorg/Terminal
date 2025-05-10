# source\services\vault\config\vault.hcl

ui = true
disable_mlock = true
log_level = "info"
api_addr = "http://vault-service:8200"

storage "file" {
  path = "/vault/file"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}
