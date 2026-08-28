FROM python:3.11-slim
WORKDIR /app

# Diagnostic utilities (ping, dig, curl, netstat)
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping dnsutils curl net-tools \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

# Security: non-root user (matches mesh-agent UID convention)
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

EXPOSE 8111

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8111/healthz || exit 1
CMD ["python", "app.py"]
