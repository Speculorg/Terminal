FROM rabbitmq:4.0.7-management

LABEL maintainer="Speculorg Team"

USER root

# --- Install python3 and pip ---
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 python3-pip curl && \
    pip3 install --break-system-packages --no-cache-dir requests && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/local/bin:${PATH}"

# --- Entrypoint: register in Consul and start RabbitMQ ---
ENTRYPOINT ["bash", "-c", "python3 /opt/scripts/register_in_consul.py && exec docker-entrypoint.sh rabbitmq-server"]
