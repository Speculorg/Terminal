# services/vault/config/vault_https.hcl
# Secure mode: HTTPS+mTLS. Consul storage тоже по HTTPS.

ui = true
disable_mlock = true
log_level = "info"
api_addr = "https://vault:8200"

listener "tcp" {
  address = "0.0.0.0:8200"
  cluster_address = "0.0.0.0:8201"

  tls_cert_file = "/fs/terminal/certs/vault.crt"
  tls_key_file  = "/fs/terminal/certs/vault.key"

  tls_client_ca_file = "/fs/terminal/certs/ca.crt"
  tls_require_and_verify_client_cert = true
  tls_disable_client_certs = false
}

storage "consul" {
  address = "consul:8501"
  scheme  = "https"
  path    = "vault/"

  tls_ca_file   = "/fs/terminal/certs/ca.crt"
  tls_cert_file = "/fs/terminal/certs/vault.crt"
  tls_key_file  = "/fs/terminal/certs/vault.key"
}
