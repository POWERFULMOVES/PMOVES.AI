FROM python:3.12-slim

WORKDIR /app

# Install Python deps. nats-py is the only NATS client; everything
# else is FastAPI + Pydantic.
COPY pmoves/services/nats_event_bus/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the service module + the contract schemas it validates against.
COPY pmoves/services/nats_event_bus /app/nats_event_bus
COPY pmoves/services/common /app/services/common
COPY pmoves/contracts /app/contracts

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PMOVES_CONTRACTS_DIR=/app/contracts \
    NATS_EVENT_BUS_PORT=8131 \
    NATS_EVENT_BUS_HOST=0.0.0.0

EXPOSE 8131

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8131/healthz').status == 200 else 1)"

CMD ["uvicorn", "nats_event_bus.app:app", "--host", "0.0.0.0", "--port", "8131"]
