# Python Layer – UBI 9 + Python 3.11
FROM registry.access.redhat.com/ubi9/python-311 AS py
RUN pip install --no-cache-dir requests

# Keycloak Layer
FROM quay.io/keycloak/keycloak:26.1.3

USER root

# Copy Python from previous stage
COPY --from=py /usr /usr
COPY --from=py /lib64 /lib64
COPY --from=py /lib /lib
COPY --from=py /opt /opt
ENV PATH="/usr/bin:/usr/local/bin:$PATH"

# Realm import
COPY realm-import.json /opt/keycloak/data/import/realm-import.json
ENV KC_IMPORT=/opt/keycloak/data/import/realm-import.json

ENTRYPOINT ["sh", "-c", "python3 /opt/scripts/register_in_consul.py && exec /opt/keycloak/bin/kc.sh start-dev"]
