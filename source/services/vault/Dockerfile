FROM python:3.13-alpine AS py

LABEL maintainer="Speculorg Team"

# hadolint ignore=DL3013
RUN pip install --no-cache-dir requests

FROM hashicorp/vault:1.19.0

# hadolint ignore=DL3002
USER root

COPY --from=py /usr/local /usr/local
ENV PATH="/usr/local/bin:${PATH}"

ENV VAULT_ADDR=http://0.0.0.0:8200

ENTRYPOINT ["sh", "-c", "python3 /opt/scripts/register_in_consul.py && exec /usr/local/bin/docker-entrypoint.sh vault server -dev -dev-listen-address=0.0.0.0:8200"]
