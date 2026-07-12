# PMOVES gateway service Dockerfile
# Build context: repo root (pmoves/)
# Usage: docker build -f services/gateway/Dockerfile -t pmoves-gateway:latest .
FROM python:3.11-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY services/gateway/requirements.txt services/gateway/requirements.lock ./
RUN pip install --no-cache-dir --constraint requirements.lock -r requirements.txt

# PMOVES package namespace + shared libraries
COPY __init__.py /app/pmoves/__init__.py
COPY services/__init__.py /app/pmoves/services/__init__.py
COPY services/common /app/pmoves/services/common
COPY services/gateway /app/pmoves/services/gateway

# PMOVES shared tools (imported by gateway as pmoves.tools.*)
COPY tools/__init__.py /app/pmoves/tools/__init__.py
COPY tools/chit_common.py /app/pmoves/tools/chit_common.py
COPY tools/chit_security.py /app/pmoves/tools/chit_security.py

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app


# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
USER pmoves:pmoves

EXPOSE 8085

# Health check (gateway has no dedicated /healthz — probe root)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8085/ || exit 1
CMD ["uvicorn", "pmoves.services.gateway.gateway.main:app", "--host", "0.0.0.0", "--port", "8085"]
