FROM python:3.13-alpine AS py

LABEL maintainer="Speculorg Team"

# hadolint ignore=DL3013
RUN pip install --no-cache-dir requests

FROM timescale/timescaledb:2.19.0-pg17

# hadolint ignore=DL3002
USER root

COPY --from=py /usr/local /usr/local
ENV PATH="/usr/local/bin:${PATH}"

ENTRYPOINT ["sh", "-c", "python3 /opt/scripts/register_in_consul.py && exec /usr/local/bin/docker-entrypoint.sh postgres"]
