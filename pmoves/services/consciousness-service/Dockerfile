FROM python:3.12-slim

# Security: Run as non-root user
RUN groupadd -r pmoves && useradd -r -g pmoves pmoves

WORKDIR /app

# Install system dependencies for sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (cache layer)
COPY services/consciousness-service/requirements.txt services/consciousness-service/requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

# Copy application code
COPY services/consciousness-service/*.py ./

# PMOVES namespace + shared tools (imported as pmoves.tools.*)
RUN mkdir -p /app/pmoves \
    && printf '"""Minimal pmoves namespace for Docker."""\n' > /app/pmoves/__init__.py
COPY tools/__init__.py /app/pmoves/tools/__init__.py
COPY tools/zeta_filter.py /app/pmoves/tools/zeta_filter.py
# cgp_mapper imports pmoves.chit (CGP_SPEC_VERSION) unconditionally, and
# chr_algorithm prefers the canonical pmoves.tools.chit_security signer.
COPY chit/__init__.py /app/pmoves/chit/__init__.py
COPY tools/chit_common.py /app/pmoves/tools/chit_common.py
COPY tools/chit_security.py /app/pmoves/tools/chit_security.py

# services/common/env.py — CHIT passphrase + secret helpers (imported as services.common.env)
RUN mkdir -p /app/services/common
COPY services/common/__init__.py /app/services/common/__init__.py
COPY services/common/env.py /app/services/common/env.py

# Set ownership
RUN chown -R pmoves:pmoves /app

# Switch to non-root user
USER pmoves

# Environment defaults
ENV SERVICE_NAME=consciousness-service
ENV SERVICE_PORT=8106
ENV NATS_URL=nats://nats:pmoves@nats:4222
# CHIT_PROD_PASSPHRASE injected at runtime via docker-compose
ENV SUPABASE_URL=http://supabase-kong:8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8106

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8106/healthz').raise_for_status()"

CMD ["python", "main.py"]
