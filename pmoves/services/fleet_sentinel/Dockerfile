FROM python:3.12-slim

# Self-contained context: only services/fleet_sentinel/ is COPYed. The NATS
# listener imports services.common.nats_service_listener -> service_registry,
# which imports supabase at module level (service_registry.py:35) — the full
# dependency set is required even though the sentinel keeps its own cache.
WORKDIR /app

COPY services/fleet_sentinel/ /app/services/fleet_sentinel/

RUN pip install --no-cache-dir fastapi uvicorn nats-py httpx supabase

ENV PYTHONPATH=/app \
    SENTINEL_PORT=8099

EXPOSE 8099

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8099/healthz', timeout=4)"

CMD ["uvicorn", "services.fleet_sentinel.main:app", "--host", "0.0.0.0", "--port", "8099"]
