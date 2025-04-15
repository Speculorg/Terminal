FROM python:3.13.1-slim

WORKDIR /app

COPY ./docker/infrastructure-elk-module/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./modules/infrastructure-elk-module/ .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV SERVICE_PORT=9104
ENV SERVICE_HOST=0.0.0.0
ENV SERVICE_NAME=infrastructure-elk-module

# Health check configuration
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD ["curl", "-f", "http://localhost:9104/health"]

# Expose port for service
EXPOSE 9104

# Start application
ENTRYPOINT ["python", "main.py"]