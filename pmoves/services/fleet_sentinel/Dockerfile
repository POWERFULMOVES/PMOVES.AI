FROM python:3.12-slim

WORKDIR /app

COPY services/fleet_sentinel/ /app/services/fleet_sentinel/
COPY services/common/ /app/services/common/

RUN pip install --no-cache-dir fastapi uvicorn

ENV PYTHONPATH=/app \
    SENTINEL_PORT=8099

EXPOSE 8099

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8099/healthz', timeout=4)"

CMD ["uvicorn", "services.fleet_sentinel.main:app", "--host", "0.0.0.0", "--port", "8099"]
