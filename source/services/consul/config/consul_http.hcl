# source\services\consul\config\consul_http.hcl


datacenter = "dc-1"
node_name = "node-1"
server = true
bootstrap_expect = 1
data_dir = "/consul/data"
disable_update_check = true

ui_config { enabled = true }

addresses {
  http = "0.0.0.0"
  dns = "0.0.0.0"
}

ports {
  http = 8500
  grpc = 8502
  dns = 8600
}

acl {
  enabled = true
  default_policy = "deny"
  enable_token_persistence = true
}
