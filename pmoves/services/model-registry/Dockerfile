# PMOVES Model Registry Service Dockerfile
# Dynamic model configuration service - Supabase-backed model registry
# Base image pinned 2026-03-05 — refresh monthly or via Dependabot
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY services/model-registry/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user (PMOVES standard: UID/GID 65532)
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves

# Copy application and the shared PMOVES modules it imports at startup.
COPY --chown=pmoves:pmoves services/model-registry/*.py .
RUN mkdir -p /app/pmoves/services /app/pmoves/tools /app/pmoves/config /app/pmoves/contracts
COPY --chown=pmoves:pmoves __init__.py /app/pmoves/__init__.py
COPY --chown=pmoves:pmoves services/__init__.py /app/pmoves/services/__init__.py
COPY --chown=pmoves:pmoves services/common /app/pmoves/services/common
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
    CMD curl -f http://localhost:8110/healthz || exit 1

# Run the application
EXPOSE 8110

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8110"]
