FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app:/app/libs

# Install curl for health checks in wait-for-deps.sh
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip
# With build context at repo root
COPY libs /app/libs
COPY services/common /app/services/common
COPY services/hi-rag-gateway-v2/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY services/hi-rag-gateway-v2/ ./
# Include local scripts for seeding and startup
COPY services/hi-rag-gateway-v2/scripts /app/scripts
COPY tools/chit_security.py /app/tools/chit_security.py

# Make wait-for-deps.sh executable
RUN chmod +x /app/scripts/wait-for-deps.sh

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

EXPOSE 8086

# Use wait-for-deps.sh as entrypoint to wait for Supabase realtime before starting
ENTRYPOINT ["/app/scripts/wait-for-deps.sh"]
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8086"]
