datacenter = "dc1"
node_name   = "consul"
server      = true
bootstrap_expect = 1

bind_addr   = "0.0.0.0"

# Runtime: HTTPS доступен в docker-сети/хосте (в TERM-1 на одном хосте).
client_addr = "0.0.0.0"

ui_config {
  enabled = true
}

ports {
  http  = -1
  https = 8501
}

data_dir = "/consul/data"
log_level = "INFO"

tls {
  defaults {
    ca_file   = "/fs/terminal/certs/ca.crt"
    cert_file = "/fs/terminal/certs/consul.crt"
    key_file  = "/fs/terminal/certs/consul.key"

    verify_incoming = true
    verify_outgoing = true
  }

  internal_rpc {
    # Для single-node TERM-1 оставляем без проверки hostname.
    verify_server_hostname = false
  }
}

acl {
  enabled                  = true
  default_policy           = "deny"
  enable_token_persistence = true
}
