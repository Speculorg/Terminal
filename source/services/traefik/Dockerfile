# File: source/services/traefik/Dockerfile

# Use the official Traefik v3.3.4 image as base
FROM traefik:v3.3.4

# Copy our static configuration into the container
# Traefik will look for /etc/traefik/traefik.yml by default
COPY traefik.yml /etc/traefik/traefik.yml

# Expose the dashboard port
EXPOSE 9000

# No CMD or ENTRYPOINT needed, we rely on docker-compose 'command' to pass flags
# If omitted, the image's default ENTRYPOINT is used (the traefik binary)
