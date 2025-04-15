FROM python:3.13.1-slim

WORKDIR /app

COPY ./docker/management-service/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./services/management-service/ .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV SERVICE_PORT=9001
ENV SERVICE_HOST=0.0.0.0
ENV SERVICE_NAME=management-service

# Health check configuration
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD ["curl", "-f", "http://localhost:9001/health"]

# Expose port for service
EXPOSE 9001

# Start application
ENTRYPOINT ["python", "main.py"]