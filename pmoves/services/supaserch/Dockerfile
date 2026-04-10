# Needs apt-get for system libs (curl) — cannot use DHI; pinned digest
FROM python:3.11-slim@sha256:d6e4d224f70f9e0172a06a3a2eba2f768eb146811a349278b38fff3a36463b47
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/supaserch/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    "setuptools==82.0.0" "wheel==0.46.3" \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY services/supaserch /app/services/supaserch
COPY services/common /app/services/common
COPY services/__init__.py /app/services/__init__.py
ENV PYTHONPATH=/app
ENV SUPASERCH_PORT=8099

# Security: Run as non-root user (PMOVES standard: UID/GID 65532)
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves


# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8099/health || exit 1
CMD ["uvicorn", "services.supaserch.app:app", "--host", "0.0.0.0", "--port", "8099"]
