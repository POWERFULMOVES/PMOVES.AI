# PMOVES.AI Hardened Ultimate-TTS-Studio
# Multi-engine TTS with all 7 engines pre-installed
# Following PMOVES.AI security standards: non-root, health checks, minimal surface

ARG CUDA_VERSION=12.4.1
ARG PYTHON_VERSION=3.10

# =============================================================================
# Stage 1: Builder - Install all dependencies
# =============================================================================
FROM nvidia/cuda:${CUDA_VERSION}-cudnn-devel-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System dependencies for TTS engines
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    build-essential \
    espeak-ng \
    libespeak-ng1 \
    libespeak-ng-dev \
    portaudio19-dev \
    libportaudio2 \
    libaio-dev \
    ffmpeg \
    libsndfile1 \
    libsox-dev \
    sox \
    python3.10 \
    python3.10-venv \
    python3.10-dev \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python3.10 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip wheel setuptools

# Clone Ultimate-TTS-Studio
WORKDIR /build
RUN git clone --depth 1 https://github.com/SUP3RMASS1VE/Ultimate-TTS-Studio-SUP3R-Edition.git app

WORKDIR /build/app

# Install core dependencies first (order matters for compatibility)
RUN pip install --no-cache-dir \
    torch==2.5.1 \
    torchaudio==2.5.1 \
    --index-url https://download.pytorch.org/whl/cu124

# Install TTS engines explicitly (these are the 7 we need)
RUN pip install --no-cache-dir \
    gradio>=5.0.0 \
    transformers>=4.40.0 \
    accelerate \
    einops \
    librosa \
    soundfile \
    scipy \
    numpy \
    pydub \
    resampy

# Install KittenTTS from wheel
RUN pip install --no-cache-dir \
    https://github.com/devilismyfriend/KittenTTS/releases/download/0.0.1.2/kittentts-0.0.1.2-py3-none-any.whl

# Install Kokoro TTS
RUN pip install --no-cache-dir kokoro misaki

# Install F5-TTS
RUN pip install --no-cache-dir f5-tts

# Install VoxCPM and Whisper
RUN pip install --no-cache-dir voxcpm openai-whisper

# Install remaining requirements (skip already installed)
COPY requirements-ultimate-tts.txt /build/
RUN pip install --no-cache-dir -r /build/requirements-ultimate-tts.txt 2>/dev/null || true

# Install phonemizer-fork (must be after phonemizer uninstall)
RUN pip uninstall -y phonemizer 2>/dev/null || true && \
    pip install --no-cache-dir phonemizer-fork

# Install onnxruntime-gpu
RUN pip install --no-cache-dir --upgrade --force-reinstall onnxruntime-gpu==1.22.0

# Download spacy model
RUN pip install --no-cache-dir spacy && \
    python -m spacy download en_core_web_sm || true

# =============================================================================
# Stage 2: Runtime - Minimal production image
# =============================================================================
FROM nvidia/cuda:${CUDA_VERSION}-cudnn-runtime-ubuntu22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"
ENV GRADIO_SERVER_NAME="0.0.0.0"
ENV GRADIO_SERVER_PORT="7861"

# Runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    libespeak-ng1 \
    portaudio19-dev \
    libportaudio2 \
    libaio1 \
    ffmpeg \
    libsndfile1 \
    libsox3 \
    sox \
    python3.10 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user following PMOVES.AI standards (UID 65532)
RUN groupadd -g 65532 pmoves && \
    useradd -u 65532 -g pmoves -d /app -s /bin/bash pmoves

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --from=builder /build/app /app

# Create directories for models and checkpoints
RUN mkdir -p /app/checkpoints /app/outputs /app/models && \
    chown -R pmoves:pmoves /app

# Set working directory
WORKDIR /app

# Switch to non-root user
USER pmoves

# Expose Gradio port
EXPOSE 7861

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:7861/gradio_api/info || exit 1

# Launch script
CMD ["python", "launch.py", "--share=false", "--listen"]
