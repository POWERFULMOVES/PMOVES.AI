FROM python:3.12-slim

LABEL org.opencontainers.image.title="PMOVES Semantic Cache"
LABEL org.opencontainers.image.description="pgvector-powered semantic cache proxy for LLM inference (#1427)"
LABEL org.opencontainers.image.source="https://github.com/POWERFULMOVES/PMOVES.AI"

# Security: run as non-root
RUN groupadd -r cache && useradd -r -g cache -s /sbin/nologin cache

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY --chown=cache:cache . .

USER cache

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:3001/healthz')" || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001"]
