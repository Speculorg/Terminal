# Dockerfile for security.service
FROM python:3.13-slim

# hadolint ignore=DL3018
# RUN apk add --no-cache curl

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app
CMD ["python", "-m", "http.server", "8000"]
