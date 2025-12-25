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

RUN pip install --no-cache-dir --upgrade pip

# With build context at pmoves/ root
COPY services/common /app/services/common
COPY services/media-audio/requirements.txt ./
COPY services/media-audio/requirements.lock ./
RUN pip install --no-cache-dir --constraint requirements.lock -r requirements.txt
# services/common requires jsonschema (installed separately to avoid hash conflict)
RUN pip install --no-cache-dir jsonschema>=4.0.0
COPY services/media-audio/ ./

# Security: Run as non-root user (GPU services need video group)
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves -G video --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

EXPOSE 8082
CMD ["uvicorn","server:app","--host","0.0.0.0","--port","8082"]
