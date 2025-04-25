#!/bin/sh
# vault-bootstrap.sh
# Put basic connection strings into Vault KV after the dev Vault is unsealed.

VAULT_ADDR=http://vault.service:8200
VAULT_TOKEN=root

vault login -no-print $VAULT_TOKEN

vault kv put secret/postgres url="postgresql://speculorg:speculpwd@database.service:5432/speculorg"
vault kv put secret/rabbitmq url="amqp://guest:guest@rabbitmq.service:5672//"
vault kv put secret/redis    url="redis://redis.service:6379/0"

echo "Vault bootstrap finished."
