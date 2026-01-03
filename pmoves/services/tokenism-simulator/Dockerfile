# PMOVES Tokenism Simulator
# Hardened service following PMOVES.AI patterns

ARG PYTHON_BASE=python:3.11-slim

FROM ${PYTHON_BASE}

# Set metadata
LABEL maintainer="PMOVES.AI <hello@powerfulmoves.com>"
LABEL description="Token economy simulation service for PMOVES.AI"
LABEL version="1.0.0"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for PMOVES hardening
RUN useradd -m -u 1001 pmoves && \
    chown -R pmoves:pmoves /app

# Switch to non-root user
USER pmoves

# Expose port
EXPOSE 8100

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8100/healthz')" || exit 1

# Run with gunicorn in production
CMD ["gunicorn", "--bind", "0.0.0.0:8100", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:create_app()"]
