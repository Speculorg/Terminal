datacenter = "dc1"
node_name   = "consul"
server      = true
bootstrap_expect = 1

bind_addr   = "0.0.0.0"

# Bootstrap-окно: HTTP только на loopback внутри контейнера.
client_addr = "127.0.0.1"

ui_config {
  enabled = true
}

ports {
  http  = 8500
  https = -1
}

data_dir = "/consul/data"
log_level = "INFO"

acl {
  enabled                  = true
  default_policy           = "deny"
  enable_token_persistence = true
}
