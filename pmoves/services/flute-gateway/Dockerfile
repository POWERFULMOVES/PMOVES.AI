FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/POWERFULMOVES/PMOVES.AI"
LABEL org.opencontainers.image.description="Flute Gateway - Multimodal Voice Communication Layer"

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY services/flute-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user for security
RUN useradd --create-home --shell /bin/bash pmoves

# Copy source
COPY services/flute-gateway/ .

# Change ownership to non-root user
RUN chown -R pmoves:pmoves /app

# Switch to non-root user
USER pmoves

# Environment
ENV FLUTE_HTTP_PORT=8055
ENV FLUTE_WS_PORT=8056

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8055/healthz || exit 1

EXPOSE 8055 8056

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8055"]
