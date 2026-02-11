# PMOVES DeepResearch - LLM-based Research Planner
# Multi-stage hardened build following PMOVES.AI security standards
#
# NOTE: This service builds from the upstream Alibaba-NLP/DeepResearch project.
# The external source is pinned to a specific commit for reproducibility.

ARG PYTHON_BASE=python:3.10-slim

# ===== Stage 1: Builder =====
FROM ${PYTHON_BASE}@sha256:e508a34e5491225a76fbb9e0f43ebde1f691c6a689d096d7510cf7fb17d4ba6f AS builder

# Build arguments for external dependency
ARG DEEPRESEARCH_REPO=https://github.com/Alibaba-NLP/DeepResearch.git
ARG DEEPRESEARCH_COMMIT=3f2845ffea03f198a84716a580e2cbb4145b0465

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Clone external DeepResearch source at pinned commit
# Note: Using --depth 1 with --branch requires full commit history fetch
RUN git clone --depth 1 "${DEEPRESEARCH_REPO}" /opt/DeepResearch && \
    cd /opt/DeepResearch && \
    git fetch origin "${DEEPRESEARCH_COMMIT}" && \
    git checkout "${DEEPRESEARCH_COMMIT}"

# Install Python requirements with hash verification
# NOTE: We install both our requirements.lock and the upstream requirements.txt
COPY services/deepresearch/requirements.lock .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --require-hashes -r requirements.lock --target /install && \
    pip install --no-cache-dir -r /opt/DeepResearch/requirements.txt --target /install

# ===== Stage 2: Runtime =====
FROM ${PYTHON_BASE}@sha256:e508a34e5491225a76fbb9e0f43ebde1f691c6a689d096d7510cf7fb17d4ba6f

# Metadata labels
LABEL maintainer="PMOVES.AI <infra@pmoves.ai>" \
      org.opencontainers.image.title="PMOVES DeepResearch" \
      org.opencontainers.image.description="LLM-based research planning service (Alibaba Tongyi DeepResearch)" \
      org.opencontainers.image.vendor="PMOVES.AI" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/powerfulmoves/PMOVES-Deep-Serch" \
      pmoves.upstream.repo="https://github.com/Alibaba-NLP/DeepResearch.git" \
      pmoves.upstream.commit="3f2845ffea03f198a84716a580e2cbb4145b0465"

# Runtime environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PMOVES_CONTRACTS_DIR=/app/contracts

WORKDIR /app

# Install ONLY runtime dependencies (curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy external DeepResearch source (needed for imports)
COPY --from=builder /opt/DeepResearch /opt/DeepResearch

# Copy application code
COPY services/deepresearch /app/services/deepresearch
COPY services/common /app/services/common
COPY services/__init__.py /app/services/__init__.py
COPY contracts /app/contracts

# Security: Create non-root user with PMOVES standard UID/GID
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app && \
    chown -R pmoves:pmoves /opt/DeepResearch

USER pmoves:pmoves

# Health check endpoint for orchestration
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8098/healthz || exit 1

EXPOSE 8098

CMD ["python", "-m", "services.deepresearch.worker"]
