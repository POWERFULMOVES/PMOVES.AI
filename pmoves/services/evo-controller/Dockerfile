# Base image pinned 2026-03-05 — refresh monthly or via Dependabot
FROM python:3.11-slim

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
