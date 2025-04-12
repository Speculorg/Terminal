FROM python:3.13.1-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./services/security-service/ .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV SERVICE_PORT=9002
ENV SERVICE_HOST=0.0.0.0
ENV SERVICE_NAME=security-service

# Health check configuration
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD ["curl", "-f", "http://localhost:9002/health"]

# Expose port for service
EXPOSE 9002

# Start application
ENTRYPOINT ["python", "main.py"]