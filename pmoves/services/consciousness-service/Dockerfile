FROM python:3.12-slim

# Security: Run as non-root user
RUN groupadd -r pmoves && useradd -r -g pmoves pmoves

WORKDIR /app

# Install dependencies first (cache layer)
COPY requirements.txt requirements.lock .
RUN pip install --no-cache-dir --constraint requirements.lock -r requirements.txt

# Copy application code
COPY *.py ./

# Set ownership
RUN chown -R pmoves:pmoves /app

# Switch to non-root user
USER pmoves

# Environment defaults
ENV SERVICE_NAME=consciousness-service
ENV SERVICE_PORT=8096
ENV NATS_URL=nats://nats:4222
ENV HIRAG_V2_URL=http://hi-rag-gateway-v2:8086

EXPOSE 8096

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8096/healthz').raise_for_status()"

CMD ["python", "main.py"]
