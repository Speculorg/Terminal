FROM python:3.13-alpine AS py

RUN pip install --no-cache-dir \
    requests \
    pydantic \
    pydantic-settings

FROM hashicorp/consul:1.20.5

USER root

COPY --from=py /usr/local /usr/local

ENV PATH="/usr/local/bin:$PATH"

ENTRYPOINT ["python3", "/app/main.py"]
