FROM python:3.11-slim

WORKDIR /app

# Pinokio bridge reads ~/pinokio/ on the host — keep the container's
# home dir bind-mountable. The PINOKIO_HOME env var can override.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PINOKIO_BRIDGE_PORT=8130

# Build context is the monorepo root (matching the documented
# `docker build -f pmoves/services/pinokio_bridge/Dockerfile .`).
# Install Python deps from the service-local requirements.txt.
COPY pmoves/services/pinokio_bridge/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the service module + the contract schemas / common code it
# imports. Same layout as the nats_event_bus / a2ui-nats-bridge /
# p7-room-orchestrator Dockerfiles: service module at /app/<name>.
COPY pmoves/services/pinokio_bridge /app/pinokio_bridge
COPY pmoves/services/common /app/services/common
COPY pmoves/contracts /app/contracts

EXPOSE 8130

# Run as the pmoves user (matches compose file's user directive)
RUN useradd --create-home --shell /bin/bash pmoves 2>/dev/null || true
USER pmoves

CMD ["uvicorn", "pinokio_bridge.app:app", \
     "--host", "0.0.0.0", "--port", "8130"]
