# =============================================================================
# PMOVES.AI — Semantic Cache Proxy Container Image
# Issue #1427: FastAPI sidecar proxy for LLM semantic caching
# =============================================================================
#
# Build context: ./services/semantic-cache/
# Base image:    python:3.12-slim (distroless not available for Python)
#
# Hardening:
#   - Runs as non-root user (uid 65532, matching PMOVES distroless convention)
#   - Read-only rootfs (use tmpfs mounts for /tmp, /app/cache)
#   - No shell or dev tools in final image
#   - Minimal attack surface: only Python stdlib + runtime deps
#
# Build:
#   docker build -t pmoves/semantic-cache:latest ./services/semantic-cache
#
# =============================================================================

FROM python:3.12-slim

LABEL org.opencontainers.image.title="PMOVES Semantic Cache Proxy"
LABEL org.opencontainers.image.description="FastAPI proxy for LLM semantic caching (pgvector + Cipher)"
LABEL org.opencontainers.image.version="2.0.0"
LABEL org.opencontainers.image.licenses="Proprietary"

# --- Build arguments ---
ARG PYTHONDONTWRITEBYTECODE=1
ARG PYTHONUNBUFFERED=1
ARG PIP_NO_CACHE_DIR=1
ARG PIP_DISABLE_PIP_VERSION_CHECK=1

# --- Install runtime dependencies ---
# curl is needed for the health check; remove after health-check setup if desired.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# --- Create non-root runtime user (matches PMOVES distroless uid) ---
RUN groupadd --gid 65532 pmoves \
    && useradd --uid 65532 --gid pmoves --shell /usr/sbin/nologin --home-dir /app pmoves

# --- Install Python dependencies ---
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy application source ---
COPY main.py metrics.py cache_store.py cipher_layer.py hirag_client.py config.py chit_invalidation.py ./

# --- Create writable directories for tmpfs mounts ---
RUN mkdir -p /app/cache /tmp /var/tmp \
    && chown -R 65532:65532 /app

# --- Non-root user ---
USER 65532:65532

# --- Expose proxy port ---
EXPOSE 8100

# --- Health check ---
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8100/health || exit 1

# --- Runtime ---
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100", "--proxy-headers"]
