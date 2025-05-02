datacenter = "speculorg-dev"
node_name = "consul-node-1"
server = true
bootstrap_expect = 1
data_dir = "/consul/data"
enable_central_service_config = true
log_level = "INFO"
enable_syslog = false
disable_update_check = true


ui_config {
  enabled = true
}


addresses {
  http = "0.0.0.0"
  # dns  = "0.0.0.0"
}


ports {
  http = 8500
  grpc = 8502
  # dns  = 8600
}


# tls {
#   http = true
#   grpc = true
#   ca_file = "/etc/consul/certs/ca.pem"
#   cert_file = "/etc/consul/certs/consul.pem"
#   key_file  = "/etc/consul/certs/consul-key.pem"
#   verify_incoming = false
#   verify_outgoing = true
# }
