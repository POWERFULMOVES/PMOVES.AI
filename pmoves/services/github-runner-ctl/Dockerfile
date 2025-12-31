FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/POWERFULMOVES/PMOVES.AI"
LABEL org.opencontainers.image.description="GitHub Runner Controller - PMOVES CI/CD Orchestration"

WORKDIR /app

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8100

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Non-root user for security (PMOVES pattern)
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

# Switch to non-root user
USER pmoves:pmoves

# Health check (PMOVES standard pattern)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["sh", "-c", "curl -f http://localhost:${PORT:-8100}/healthz || exit 1"]

EXPOSE 8100

# Use shell to expand ${PORT} environment variable
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
