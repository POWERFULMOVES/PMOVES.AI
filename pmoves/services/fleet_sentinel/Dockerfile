FROM python:3.12-slim

# Build context is the pmoves/ dir (compose: context: . / dockerfile:
# services/fleet_sentinel/Dockerfile) so services/common/ ships in-image. The
# NATS listener imports services.common.nats_service_listener ->
# service_registry, which imports supabase at module level
# (service_registry.py:35) — the full dependency set is required even though
# the sentinel keeps its own cache. Without services/common the listener falls
# back to its minimal in-file subscriber.
WORKDIR /app

COPY services/fleet_sentinel/ /app/services/fleet_sentinel/
COPY services/common/ /app/services/common/

RUN pip install --no-cache-dir fastapi uvicorn nats-py httpx supabase

# 8116: 8099 is SupaSerch's published host port (CATALOG.md); the anchors
# ratchet drops any port two services publish, which is how the collision
# surfaced (STALE_BASELINE on supaserch.md's localhost:8099 citation).
ENV PYTHONPATH=/app \
    SENTINEL_PORT=8116

EXPOSE 8116

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8116/healthz', timeout=4)"

# Non-root (hardened fleet posture; hardening_ratchet requires a non-root
# USER as the final USER directive).
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

CMD ["uvicorn", "services.fleet_sentinel.main:app", "--host", "0.0.0.0", "--port", "8116"]
