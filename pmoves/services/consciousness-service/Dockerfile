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
COPY requirements.txt requirements.lock .
RUN pip install --no-cache-dir --constraint requirements.lock -r requirements.txt

# Copy application code
COPY *.py ./

# Copy pmoves tools (chit_security, geometry_decoder) via volume mount or copy
# These are expected to be available at runtime via /app/pmoves/tools

# Set ownership
RUN chown -R pmoves:pmoves /app

# Switch to non-root user
USER pmoves

# Environment defaults
ENV SERVICE_NAME=consciousness-service
ENV SERVICE_PORT=8105
ENV NATS_URL=nats://nats:pmoves@nats:4222
# CHIT_PROD_PASSPHRASE injected at runtime via docker-compose
ENV SUPABASE_URL=http://supabase-kong:8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8105

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8105/healthz').raise_for_status()"

CMD ["python", "main.py"]
