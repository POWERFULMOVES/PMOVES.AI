# GPU Orchestrator Service Dockerfile
# ====================================
# Uses shared CUDA base image for GPU access via pynvml.
#
# Build: docker build -t pmoves/gpu-orchestrator:latest .

ARG CUDA_BASE_TAG=12.8.1
FROM pmoves/cuda-base:${CUDA_BASE_TAG} AS base

# Switch to root for package installation
USER root

# Install Docker CLI for container introspection
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy config directory for model registry
RUN mkdir -p /app/config

# Fix permissions for pmoves user
RUN chown -R pmoves:pmoves /app

# Set environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    GPU_ORCHESTRATOR_HOST=0.0.0.0 \
    GPU_ORCHESTRATOR_PORT=8200

# Switch back to non-root user
USER pmoves

# Expose port
EXPOSE 8200

# Health check
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8200/healthz || exit 1

# Run the service
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8200"]
