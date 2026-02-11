# PMOVES.YT - YouTube Ingestion Service
# Multi-stage hardened build following PMOVES.AI security standards

# ===== Stage 1: Builder =====
# Install build-time dependencies and compile Python packages
FROM python:3.11-slim@sha256:0b23cfb7425d065008b778022a17b1551c82f8b4866ee5a7a200084b7e2eafbf AS builder

# Build arguments for yt-dlp flexibility
ARG YTDLP_VERSION=
ARG YTDLP_PIP_URL=

WORKDIR /build

# Install build dependencies (not needed at runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements with hash verification
# Using --target to isolate installed packages
COPY requirements.lock .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --require-hashes -r requirements.lock --target /install && \
    # Handle yt-dlp installation (may need build deps)
    if [ -n "$YTDLP_PIP_URL" ]; then \
        pip install --no-cache-dir "$YTDLP_PIP_URL" --target /install; \
    elif [ -n "$YTDLP_VERSION" ]; then \
        pip install --no-cache-dir "yt-dlp[default]==${YTDLP_VERSION}" --target /install; \
    else \
        pip install --no-cache-dir "yt-dlp[default]" --target /install; \
    fi

# ===== Stage 2: Runtime =====
# Minimal runtime image with only essential dependencies
FROM python:3.11-slim@sha256:0b23cfb7425d065008b778022a17b1551c82f8b4866ee5a7a200084b7e2eafbf

# Metadata labels
LABEL maintainer="PMOVES.AI <infra@pmoves.ai>" \
      org.opencontainers.image.title="PMOVES.YT" \
      org.opencontainers.image.description="YouTube ingestion service with transcript retrieval" \
      org.opencontainers.image.vendor="PMOVES.AI" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/powerfulmoves/PMOVES.YT"

# Runtime environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    # Prevent Python from creating .pyc files
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install ONLY runtime dependencies (ffmpeg, atomicparsley for media processing)
# Using --no-install-recommends to minimize attack surface
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    atomicparsley \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Security: Create non-root user with PMOVES standard UID/GID
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

# Health check endpoint for orchestration
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8077/healthz || exit 1

EXPOSE 8077

# Run with uvicorn
CMD ["uvicorn", "yt:app", "--host", "0.0.0.0", "--port", "8077"]
