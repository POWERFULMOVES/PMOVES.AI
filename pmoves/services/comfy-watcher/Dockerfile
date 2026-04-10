FROM python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY services/comfy-watcher/requirements.txt services/comfy-watcher/requirements.lock ./
RUN pip install --no-cache-dir --constraint requirements.lock -r requirements.txt

# Minimal app payload (common event helper + contracts + watcher)
RUN mkdir -p /app/services
COPY services/__init__.py /app/services/__init__.py
COPY services/common /app/services/common
COPY contracts /app/contracts
COPY services/comfy-watcher/README.md /app/README.md
COPY services/comfy-watcher/watcher.py /app/watcher.py

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves


# Health check (process-based for non-HTTP worker)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD test -f /proc/1/cmdline || exit 1
CMD ["python","watcher.py"]
