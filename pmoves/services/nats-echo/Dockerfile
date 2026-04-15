FROM python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir nats-py==2.8.0
# Build context is pmoves/services; use the local copy inside this folder
COPY nats-echo/nats_echo.py /app/nats_echo.py
ENV NATS_URL=nats://nats:pmoves@nats:4222 \
    NATS_ECHO_SUBJECT=research.deepresearch.request.v1

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves
# Script reads NATS_URL and NATS_ECHO_SUBJECT from the environment.

# Health check (process-based for non-HTTP worker)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD test -f /proc/1/cmdline || exit 1
CMD ["python", "/app/nats_echo.py"]
