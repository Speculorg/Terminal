FROM python:3.13-alpine AS py

# hadolint ignore=DL3013
RUN pip install --no-cache-dir \
    requests \
    pydantic \
    pydantic-settings

FROM traefik:v3.3.4

# hadolint ignore=DL3002
USER root

RUN apk add --no-cache curl

COPY --from=py /usr/local /usr/local
ENV PATH="/usr/local/bin:$PATH"

ENTRYPOINT ["python3", "/app/main.py"]
