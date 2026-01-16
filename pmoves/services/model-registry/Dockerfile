# PMOVES Model Registry Service Dockerfile
# Dynamic model configuration service - Supabase-backed model registry
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user (PMOVES standard: UID/GID 65532)
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves

# Copy application with correct ownership
COPY --chown=pmoves:pmoves main.py .

# Switch to non-root user
USER pmoves:pmoves

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8110/healthz || exit 1

# Run the application
EXPOSE 8110

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8110"]
