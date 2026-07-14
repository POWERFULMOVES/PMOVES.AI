# Needs apt-get for system libs (curl) — cannot use DHI; pinned digest
FROM python:3.11-slim@sha256:d6e4d224f70f9e0172a06a3a2eba2f768eb146811a349278b38fff3a36463b47

LABEL org.opencontainers.image.source="https://github.com/POWERFULMOVES/PMOVES.AI"
LABEL org.opencontainers.image.description="EvoSwarm Controller - Evolutionary parameter optimization service"

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (locked deps with hash verification)
COPY services/evo-controller/requirements.txt .
COPY services/evo-controller/requirements.lock .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user for security
RUN useradd --create-home --shell /bin/bash pmoves

# Copy shared common module (evo-controller imports services.common.env)
COPY services/common/ services/common/

# Canonical CHIT verifier chain: services.common.geometry_decoder imports
# pmoves.tools.chit_security and pmoves.services.common.geometry_models, so
# the pmoves package namespace must exist in the image (review #2082 P1 —
# without it the import fails and signing degrades to dev mode).
COPY __init__.py pmoves/__init__.py
COPY tools/__init__.py pmoves/tools/__init__.py
COPY tools/chit_common.py tools/chit_security.py pmoves/tools/
COPY services/__init__.py pmoves/services/__init__.py
COPY services/common/ pmoves/services/common/

# Copy source
COPY services/evo-controller/ .

# Change ownership to non-root user
RUN chown -R pmoves:pmoves /app

# Switch to non-root user
USER pmoves

# Environment
ENV PORT=8113

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8113/healthz || exit 1

EXPOSE 8113

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8113"]
