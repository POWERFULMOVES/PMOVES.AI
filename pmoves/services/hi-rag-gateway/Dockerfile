FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Base deps
RUN pip install --no-cache-dir --upgrade pip
COPY hi-rag-gateway/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- CUDA-enabled Torch for Qwen reranker (optional) ---
# If the host uses NVIDIA runtime, install CUDA wheels (cu121). This is safe on CPU-only hosts too,
# but you can skip by setting TORCH_SKIP_CUDA=1 at build time.
ARG TORCH_CUDA_VERSION=cu121
ARG TORCH_SKIP_CUDA=0
RUN if [ "$TORCH_SKIP_CUDA" != "1" ]; then pip install --no-cache-dir --index-url https://download.pytorch.org/whl/${TORCH_CUDA_VERSION} torch torchvision torchaudio || true ; else echo "Skipping CUDA Torch install"; fi

# Copy service code and shared libraries
COPY hi-rag-gateway/ .
COPY common/ ./services/common/
RUN mkdir -p /app/services && touch /app/services/__init__.py
EXPOSE 8086
CMD ["uvicorn","gateway:app","--host","0.0.0.0","--port","8086"]