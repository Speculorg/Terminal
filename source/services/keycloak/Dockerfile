# hadolint ignore=DL3006
FROM registry.access.redhat.com/ubi9/python-311 AS py

LABEL maintainer="Speculorg Team"

# hadolint ignore=DL3013
RUN pip install --no-cache-dir requests

FROM quay.io/keycloak/keycloak:26.1.3

# hadolint ignore=DL3002
USER root

COPY --from=py /usr /usr
COPY --from=py /lib64 /lib64
COPY --from=py /lib /lib
COPY --from=py /opt /opt
COPY realm-import.json /opt/keycloak/data/import/realm-import.json
ENV PATH="/usr/bin:/usr/local/bin:$PATH"
ENV KC_IMPORT=/opt/keycloak/data/import/realm-import.json

ENTRYPOINT ["sh", "-c", "python3 /opt/scripts/register_in_consul.py && exec /opt/keycloak/bin/kc.sh start-dev"]
