# PMOVES SupaSerch - Multimodal Holographic Deep Research Orchestrator
# Multi-stage hardened build following PMOVES.AI security standards

# ===== Stage 1: Builder =====
FROM python:3.11-slim@sha256:0b23cfb7425d065008b778022a17b1551c82f8b4866ee5a7a200084b7e2eafbf AS builder

WORKDIR /build

# Install build dependencies (not needed at runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements with hash verification
COPY supaserch/requirements.lock .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --require-hashes -r requirements.lock --target /install

# ===== Stage 2: Runtime =====
FROM python:3.11-slim@sha256:0b23cfb7425d065008b778022a17b1551c82f8b4866ee5a7a200084b7e2eafbf

# Metadata labels
LABEL maintainer="PMOVES.AI <infra@pmoves.ai>" \
      org.opencontainers.image.title="PMOVES SupaSerch" \
      org.opencontainers.image.description="Multimodal holographic deep research orchestrator" \
      org.opencontainers.image.vendor="PMOVES.AI" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/powerfulmoves/PMOVES-Deep-Serch"

# Runtime environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    SUPASERCH_PORT=8099

WORKDIR /app

# Install ONLY runtime dependencies (curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application code
COPY . /app/services

# Security: Create non-root user with PMOVES standard UID/GID
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

# Health check endpoint for orchestration
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8099/healthz || exit 1

EXPOSE 8099

CMD ["uvicorn", "services.supaserch.app:app", "--host", "0.0.0.0", "--port", "8099"]
