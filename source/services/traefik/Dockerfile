######## Python layer ########
FROM python:3.13-alpine AS py

LABEL maintainer="Speculorg Team"

RUN pip install --no-cache-dir requests

######## Traefik ########
FROM traefik:v3.3.4

USER root
COPY --from=py /usr/local /usr/local
ENV PATH="/usr/local/bin:${PATH}"

COPY traefik.yml /etc/traefik/traefik.yml
# COPY register_in_consul.py /opt/register_in_consul.py

ENTRYPOINT ["sh", "-c", "python3 /opt/scripts/register_in_consul.py && exec traefik"]
