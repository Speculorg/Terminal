FROM python:3.13-alpine AS py

# hadolint ignore=DL3013
RUN pip install --no-cache-dir \
    requests \
    aiohttp \
    pydantic \
    pydantic-settings

FROM hashicorp/vault:1.19.0

# hadolint ignore=DL3002
USER root

# hadolint ignore=DL3018
RUN apk add --no-cache curl

COPY --from=py /usr/local /usr/local
ENV PATH="/usr/local/bin:$PATH"

ENTRYPOINT ["python3", "/app/main.py"]
