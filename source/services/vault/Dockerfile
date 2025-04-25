FROM python:3.13-alpine AS py

LABEL maintainer="Speculorg Team"

RUN pip install --no-cache-dir requests

FROM hashicorp/vault:1.19.0
USER root
COPY --from=py /usr/local /usr/local
ENV PATH="/usr/local/bin:${PATH}"

# COPY register_in_consul.py /opt/register_in_consul.py
ENV VAULT_ADDR=http://0.0.0.0:8200

ENTRYPOINT ["sh", "-c", "python3 /opt/scripts/register_in_consul.py && exec /usr/local/bin/docker-entrypoint.sh vault server -dev -dev-listen-address=0.0.0.0:8200"]
