# GitHub Cross-Repository PR Automation Service Dockerfile
# Platform: linux/amd64, linux/arm64

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SERVICE_PORT=8104 \
    PYTHONPATH=/app

# Create non-root user for security
RUN groupadd -r pmoves && \
    useradd -r -g pmoves -u 1000 pmoves

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY --chown=pmoves:pmoves requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=pmoves:pmoves . .

# Switch to non-root user
USER pmoves

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${SERVICE_PORT}/healthz || exit 1

# Expose service port
EXPOSE 8104

# Run the application
CMD ["python", "-m", "uvicorn", "app:app", \
     "--host", "0.0.0.0", \
     "--port", "8104"]
