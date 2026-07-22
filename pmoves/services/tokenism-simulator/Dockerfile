# PMOVES Tokenism Simulator
# Hardened service following PMOVES.AI patterns

# Needs apt-get for system libs — cannot use DHI; pinned digest
FROM python:3.11-slim@sha256:d6e4d224f70f9e0172a06a3a2eba2f768eb146811a349278b38fff3a36463b47

# Set metadata
LABEL maintainer="PMOVES.AI <hello@powerfulmoves.com>"
LABEL description="Token economy simulation service for PMOVES.AI"
LABEL version="1.0.0"

# Set working directory
WORKDIR /app

# Ensure pmoves.* namespace packages import regardless of invocation cwd
# (mirrors hi-rag-gateway-v2 pattern)
ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY services/tokenism-simulator/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY services/tokenism-simulator/. .

# PMOVES namespace + shared tools (imported as pmoves.tools.*)
RUN mkdir -p /app/pmoves \
    && printf '"""Minimal pmoves namespace for Docker."""\n' > /app/pmoves/__init__.py
COPY tools/__init__.py /app/pmoves/tools/__init__.py
COPY tools/chit_common.py /app/pmoves/tools/chit_common.py
COPY tools/chit_security.py /app/pmoves/tools/chit_security.py

# services/common/env.py — CHIT passphrase + secret helpers (imported as services.common.env)
RUN mkdir -p /app/services/common
COPY services/common/__init__.py /app/services/common/__init__.py
COPY services/common/env.py /app/services/common/env.py

# pmoves.services.common.env — fallback import path (chit_encoder tries services.common.env first, falls back to this spelling on ImportError)
RUN mkdir -p /app/pmoves/services/common \
    && printf '' > /app/pmoves/services/__init__.py \
    && printf '' > /app/pmoves/services/common/__init__.py
COPY services/common/env.py /app/pmoves/services/common/env.py

# Create non-root user for PMOVES hardening
RUN useradd -m -u 1001 pmoves && \
    chown -R pmoves:pmoves /app

# Switch to non-root user
USER pmoves

# Expose port
EXPOSE 8100

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8100/healthz')" || exit 1

# Run with gunicorn in production
CMD ["gunicorn", "--bind", "0.0.0.0:8100", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:create_app()"]
