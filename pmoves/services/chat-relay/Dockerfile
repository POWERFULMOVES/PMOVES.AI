FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/POWERFULMOVES/PMOVES.AI"
LABEL org.opencontainers.image.description="Chat Relay - NATS to Supabase Realtime bridge"

WORKDIR /app

# Install dependencies
COPY services/chat-relay/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY services/chat-relay/main.py .

# Non-root user
RUN useradd -m -u 1000 pmoves
USER pmoves

# Health check using Python (curl not available in slim image)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8102/healthz', timeout=5)" || exit 1

EXPOSE 8102

CMD ["python", "main.py"]
