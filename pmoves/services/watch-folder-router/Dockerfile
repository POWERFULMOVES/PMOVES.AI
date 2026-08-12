# watch-folder-router - thin NATS router over media-audio. No models, no GPU.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && apt-get clean

WORKDIR /app
COPY pmoves/services/watch-folder-router/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock

COPY pmoves/services/watch-folder-router/worker.py /app/worker.py

EXPOSE 8125
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 CMD curl -fsS http://localhost:8125/healthz || exit 1
CMD ["uvicorn", "worker:app", "--host", "0.0.0.0", "--port", "8125"]
