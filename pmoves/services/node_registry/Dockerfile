# PMOVES Node Registry Service Dockerfile
# NATS-backed P2P node discovery and capability tracking.
#
# The port is 8115, NOT 8082. 8115 is what
# `pmoves/tests/utils/service_catalog.py` (NODE_REGISTRY.port) and
# `pmoves/docs/infrastructure/DISTRIBUTED_COMPUTE_SERVICES.md` already said;
# 8082 is media-audio's live host binding, so a service defaulting to 8082
# collides with another service and points its consumers at the wrong one.
#
# The image carries MORE than this service's own package, because the
# service's imports reach outside it:
#   - `..resource_detector.models` / `..resource_detector.hardware`
#     (api.py, registry.py, storage.py)
#   - `pmoves.services.common`, pulled in eagerly by `pmoves/services/__init__.py`
# An image that carried only services/node_registry would import cleanly on
# the host and die in the container.
#
# Base image pinned 2026-03-05 — refresh monthly or via Dependabot
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl is the healthcheck client)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY services/node_registry/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user (PMOVES standard: UID/GID 65532)
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves

# Copy the service package and everything it imports at import time.
COPY --chown=pmoves:pmoves services/node_registry /app/pmoves/services/node_registry
RUN mkdir -p /app/pmoves/services /app/pmoves/tools /app/pmoves/config /app/pmoves/contracts
COPY --chown=pmoves:pmoves __init__.py /app/pmoves/__init__.py
COPY --chown=pmoves:pmoves services/__init__.py /app/pmoves/services/__init__.py
COPY --chown=pmoves:pmoves services/common /app/pmoves/services/common
COPY --chown=pmoves:pmoves services/resource_detector /app/pmoves/services/resource_detector
COPY --chown=pmoves:pmoves tools/__init__.py /app/pmoves/tools/__init__.py
COPY --chown=pmoves:pmoves tools/chit_security.py /app/pmoves/tools/chit_security.py
COPY --chown=pmoves:pmoves tools/chit_common.py /app/pmoves/tools/chit_common.py
COPY --chown=pmoves:pmoves config/agent_signatures.yaml config/agent_registry.yaml config/signing_identity_cards.yaml /app/pmoves/config/
COPY --chown=pmoves:pmoves contracts /app/pmoves/contracts

ENV PYTHONPATH=/app \
    PMOVES_CONTRACTS_DIR=/app/pmoves/contracts

# Switch to non-root user
USER pmoves:pmoves

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8115/healthz || exit 1

# Run the application
EXPOSE 8115

CMD ["python", "-m", "pmoves.services.node_registry.main"]
