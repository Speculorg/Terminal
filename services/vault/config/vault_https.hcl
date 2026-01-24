# source\services\vault\config\vault_https.hcl


ui = true
disable_mlock = true
log_level = "info"
api_addr = "https://vault:8200"


listener "tcp" {
  address = "0.0.0.0:8200"
  cluster_address = "0.0.0.0:8201"
  tls_cert_file = "/fs/terminal/certs/vault.crt"
  tls_key_file = "/fs/terminal/certs/privkey.pem"
  tls_client_ca_file = "/fs/terminal/certs/ca.crt"
}


storage "consul" {
  address = "https://consul:8501"
  path = "vault/"
  tls_ca_file = "/fs/terminal/certs/ca.crt"
  tls_cert_file = "/fs/terminal/certs/consul.crt"
  tls_key_file = "/fs/terminal/certs/privkey.pem"
}
