# source\services\consul\config\consul_https.hcl


datacenter = "dc-1"
node_name = "node-1"
server = true
bootstrap_expect = 1
data_dir = "/consul/data"
disable_update_check = true

ui_config { enabled = true }

addresses {
  http = "0.0.0.0"
  https = "0.0.0.0"
  dns = "0.0.0.0"
}

ports {
  http = -1
  https = 8501
  grpc = 8502
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

auto_encrypt {
  allow_tls = true
}
