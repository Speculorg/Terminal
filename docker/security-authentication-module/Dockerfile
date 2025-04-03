FROM python:3.13.1-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ../../modules/security-authentication-module/ .

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:9000/health || exit 1

EXPOSE 9000

CMD ["gunicorn", "security_authentication_module.wsgi:application", "--bind", "0.0.0.0:9000"] 