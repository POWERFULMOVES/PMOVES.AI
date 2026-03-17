# ── Stage 1: Builder ─────────────────────────────────────────────
# Install build deps and compile Python wheels.  This stage is
# discarded — only the pip-installed packages survive into runtime.
# Base image pinned 2026-03-05 — refresh weekly via Dependabot
FROM python:3.11-slim@sha256:d6e4d224f70f9e0172a06a3a2eba2f768eb146811a349278b38fff3a36463b47 AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc \
       python3-dev \
       pkg-config \
       libavformat-dev \
       libavcodec-dev \
       libavdevice-dev \
       libavutil-dev \
       libswscale-dev \
       libswresample-dev \
       libavfilter-dev \
       libopus-dev \
       libvpx-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into --user prefix so we can COPY them
COPY services/flute-gateway/requirements.txt .
COPY services/flute-gateway/requirements.lock .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY services/flute-gateway/requirements-pipecat.txt .
RUN pip install --no-cache-dir --user -r requirements-pipecat.txt

# ── Stage 2: Runtime ─────────────────────────────────────────────
# Clean image with only runtime shared libs — no gcc, no -dev headers.
# Base image pinned 2026-03-05 — refresh weekly via Dependabot
FROM python:3.11-slim@sha256:d6e4d224f70f9e0172a06a3a2eba2f768eb146811a349278b38fff3a36463b47

LABEL org.opencontainers.image.source="https://github.com/POWERFULMOVES/PMOVES.AI"
LABEL org.opencontainers.image.description="Flute Gateway - Multimodal Voice Communication Layer"

WORKDIR /app

# Runtime-only system deps:
#   curl           – healthcheck
#   libavformat61 … libavfilter10 – FFmpeg 7.x shared libs for PyAV
#   libopus0       – Opus codec for aiortc/WebRTC
#   libvpx9        – VP8/VP9 codec for aiortc/WebRTC
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl \
       libavformat61 \
       libavcodec61 \
       libavdevice61 \
       libavutil59 \
       libswscale8 \
       libswresample5 \
       libavfilter10 \
       libopus0 \
       libvpx9 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN useradd --create-home --shell /bin/bash pmoves

# Copy pre-compiled Python packages from builder
COPY --from=builder /root/.local /home/pmoves/.local

# Copy shared common module (flute-gateway imports services.common.env)
COPY services/common/ services/common/

# Copy source
COPY services/flute-gateway/ .

# Change ownership to non-root user
RUN chown -R pmoves:pmoves /app

# Switch to non-root user
USER pmoves

# Ensure user-installed packages are on PATH
ENV PATH="/home/pmoves/.local/bin:${PATH}" \
    FLUTE_HTTP_PORT=8055 \
    FLUTE_WS_PORT=8056

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8055/healthz || exit 1

EXPOSE 8055 8056

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8055"]
