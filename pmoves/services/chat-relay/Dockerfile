FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/frostbytten/PMOVES.AI"
LABEL org.opencontainers.image.description="Chat Relay - NATS to Supabase Realtime bridge"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY main.py .

# Non-root user
RUN useradd -m -u 1000 pmoves
USER pmoves

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8102/healthz || exit 1

EXPOSE 8102

CMD ["python", "main.py"]
