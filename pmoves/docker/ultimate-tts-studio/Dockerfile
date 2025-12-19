# PMOVES.AI Hardened Ultimate-TTS-Studio
# Multi-engine TTS with all 7 engines (KittenTTS, Kokoro, F5-TTS, IndexTTS2, Fish, Chatterbox, VoxCPM)
# Clones from PMOVES fork: github.com/POWERFULMOVES/PMOVES-Ultimate-TTS-Studio
# Following PMOVES.AI security standards: non-root, health checks, minimal surface

ARG CUDA_VERSION=12.4.1

# =============================================================================
# Stage 1: Builder - Install all dependencies
# =============================================================================
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# System deps for audio + build utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      espeak-ng \
      libespeak-ng1 \
      libespeak-ng-dev \
      libsndfile1 \
      libportaudio2 \
      portaudio19-dev \
      libaio-dev \
      libsox-dev \
      sox \
      git \
      curl \
      build-essential \
    && rm -rf /var/lib/apt/lists/*

# Clone from PMOVES fork (synced with upstream engine fixes)
RUN git clone --depth 1 https://github.com/POWERFULMOVES/PMOVES-Ultimate-TTS-Studio.git app

WORKDIR /build/app

# Install Python deps using repo's requirements.txt (has all 7 engines)
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

# Install phonemizer-fork (must replace phonemizer)
RUN pip uninstall -y phonemizer 2>/dev/null || true && \
    pip install phonemizer-fork

# Download spacy model
RUN python -m spacy download en_core_web_sm || true

# =============================================================================
# Stage 2: Runtime - Minimal production image
# =============================================================================
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7861 \
    HF_HOME=/data/hf \
    HUGGINGFACE_HUB_CACHE=/data/hf \
    XDG_CACHE_HOME=/data/cache

# Runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      espeak-ng \
      libespeak-ng1 \
      libsndfile1 \
      libportaudio2 \
      libaio1 \
      libsox3 \
      sox \
      curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user following PMOVES.AI standards (UID 65532)
RUN groupadd -g 65532 pmoves && \
    useradd -u 65532 -g pmoves -d /app -s /bin/bash pmoves

# Copy Python environment from builder (includes all installed packages)
COPY --from=builder /opt/conda /opt/conda

# Copy application code
COPY --from=builder /build/app /app

# Create directories for models and checkpoints
RUN mkdir -p /app/checkpoints /app/outputs /app/models /data/hf /data/cache && \
    chown -R pmoves:pmoves /app /data

WORKDIR /app

# Switch to non-root user
USER pmoves

EXPOSE 7861

# Health check (start-period allows time for model loading)
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD curl -f http://localhost:7861/gradio_api/info || exit 1

CMD ["python", "launch.py"]
