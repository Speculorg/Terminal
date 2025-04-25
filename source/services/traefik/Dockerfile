FROM python:3.13-alpine AS py

LABEL maintainer="Speculorg Team"

# hadolint ignore=DL3013
RUN pip install --no-cache-dir requests

FROM traefik:v3.3.4

# hadolint ignore=DL3002
USER root

COPY --from=py /usr/local /usr/local
ENV PATH="/usr/local/bin:${PATH}"
COPY traefik.yml /etc/traefik/traefik.yml

ENTRYPOINT ["sh", "-c", "python3 /opt/scripts/register_in_consul.py && exec traefik"]
