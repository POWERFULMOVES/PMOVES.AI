# =============================================================================
# Hugging Face MCP Server for PMOVES.AI
# =============================================================================
# Provides MCP tools for model discovery, download, and management
# from Hugging Face Hub with local caching and GGUF conversion support.
# =============================================================================

FROM dhi.io/python:3.12

LABEL maintainer="PMOVES.AI <local-models@pmoves.ai>"
LABEL description="Hugging Face MCP Server for model management"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    git-lfs \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY README.md .

# Create model cache directory
RUN mkdir -p /models/hub

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/models
ENV HF_HUB_ENABLE_HF_TRANSFER=1
ENV HF_HUB_CACHE=/models/hub
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8096/health || exit 1

# Expose port
EXPOSE 8096

# Run the server
CMD ["python", "main.py"]
