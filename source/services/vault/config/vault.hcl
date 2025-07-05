# source\services\vault\config\vault.hcl

ui = true
disable_mlock = true
log_level = "info"
api_addr = "http://vault:8200"

storage "consul" {
  address = "consul:8500"
  path    = "vault/"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}
