FROM python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app

# Base deps
RUN pip install --no-cache-dir --upgrade pip
# Build context is pmoves/ (contains docker-compose.yml)
COPY services/hi-rag-gateway/requirements.txt services/hi-rag-gateway/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.txt

# --- CUDA-enabled Torch for Qwen reranker (optional) ---
# If the host uses NVIDIA runtime, install CUDA wheels (cu121). This is safe on CPU-only hosts too,
# but you can skip by setting TORCH_SKIP_CUDA=1 at build time.
ARG TORCH_CUDA_VERSION=cu121
ARG TORCH_SKIP_CUDA=0
RUN if [ "$TORCH_SKIP_CUDA" != "1" ]; then pip install --no-cache-dir --index-url https://download.pytorch.org/whl/${TORCH_CUDA_VERSION} torch torchvision torchaudio || true ; else echo "Skipping CUDA Torch install"; fi

# Copy service code and shared libraries
COPY services/hi-rag-gateway/ .
COPY services/common/ ./services/common/
RUN mkdir -p /app/services && touch /app/services/__init__.py

# PMOVES Python namespace package (for ShapeStore → pmoves.chit import)
RUN mkdir -p /app/pmoves \
    && printf '"""Minimal pmoves namespace for Docker."""\n' > /app/pmoves/__init__.py
COPY chit /app/pmoves/chit

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app


# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
USER pmoves:pmoves
EXPOSE 8086

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8086/ || exit 1
CMD ["uvicorn","gateway:app","--host","0.0.0.0","--port","8086"]