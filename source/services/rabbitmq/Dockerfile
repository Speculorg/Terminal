FROM rabbitmq:4.0.7-management

LABEL maintainer="Speculorg Team"

# hadolint ignore=DL3002
USER root

# hadolint ignore=DL3013, DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 python3-pip curl && \
    pip3 install --break-system-packages --no-cache-dir requests && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/local/bin:${PATH}"

ENTRYPOINT ["bash", "-c", "python3 /opt/scripts/register_in_consul.py && exec docker-entrypoint.sh rabbitmq-server"]
