# Media Audio Analyzer - GPU-enabled for PyTorch/Whisper
# Uses CUDA runtime for emotion detection and audio analysis models
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

# Install Python 3.11 and required system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip python3.11-dev \
    ffmpeg libsndfile1 ca-certificates curl && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
# Security: Force weights_only=True for torch.load() (prevents arbitrary code execution)
ENV TORCH_FORCE_WEIGHTS_ONLY_LOAD=1

RUN pip install --no-cache-dir --upgrade pip

# Build context is ./services/media-audio (service directory)
# Security: Reproducible builds from lockfile
COPY requirements.txt requirements.lock ./
# Install from lockfile for reproducible builds (includes hash validation)
# Security: PyTorch extra-index-url required for CUDA packages (+cu124 variants)
RUN --mount=type=cache,target=/root/.cache/pip \
    # amd64 uses the x86-resolved lock (reproducible); arm64/Jetson
    # falls back to marker-aware requirements.txt — the lock hard-pins
    # torch+cu124 wheels that do not exist for arm64 (review #2071 P2).
    if [ "$(uname -m)" = "x86_64" ]; then \
      pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cu124 -r requirements.lock; \
    else \
      pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cu124 -r requirements.txt; \
    fi
COPY . ./

# Security: Run as non-root user (GPU services need video group)
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves -G video --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

EXPOSE 8082

# Health check (GPU service — process-based, skeleton without HTTP server)
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD pgrep -f "uvicorn" || exit 1
CMD ["uvicorn","server:app","--host","127.0.0.1","--port","8082"]
