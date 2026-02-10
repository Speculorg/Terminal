# services/consul/config/consul_https.hcl
#
# Secure mode: HTTPS+mTLS.
# - HTTP is disabled (TERM-1 rule: HTTP only in bootstrap window).
# - grpc (plain) is disabled; keep grpc_tls for future needs.

datacenter = "dc-1"
node_name = "node-1"
server = true
bootstrap_expect = 1
data_dir = "/consul/data"
disable_update_check = true

ui_config { enabled = true }

# Critical: enforce IPv4 listeners in Docker network.
bind_addr   = "0.0.0.0"
client_addr = "0.0.0.0"

addresses {
  https = "0.0.0.0"
  dns = "0.0.0.0"
}

ports {
  http = -1
  https = 8501

  grpc = -1
  grpc_tls = 8503

  dns = 8600
}

acl {
  enabled = true
  default_policy = "deny"
  enable_token_persistence = true
}

tls {
  defaults {
    ca_file = "/fs/terminal/certs/ca.crt"
    cert_file = "/fs/terminal/certs/consul.crt"
    key_file = "/fs/terminal/certs/consul.key"

    verify_incoming = true
    verify_outgoing = true
  }

  internal_rpc {
    verify_server_hostname = false
  }

  https {
    verify_incoming = true
  }
}

