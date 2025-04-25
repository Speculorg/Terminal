# Consul 1.20.5 – без лишних слоёв
FROM hashicorp/consul:1.20.5

LABEL maintainer="Speculorg Team"

ENV CONSUL_FLAGS="-dev -client=0.0.0.0"

ENTRYPOINT ["sh", "-c", "exec consul agent $CONSUL_FLAGS"]
