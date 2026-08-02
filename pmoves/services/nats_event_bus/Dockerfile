FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NATS_EVENT_BUS_PORT=8131

COPY services/nats_event_bus/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY services/nats_event_bus /app/nats_event_bus
COPY services/common /app/services/common
# services.common.events resolves event schemas from /app/contracts (see
# events.py). Without this COPY, every authenticated POST /v1/publish
# raises FileNotFoundError for topics.json and the endpoint returns 422.
COPY contracts /app/contracts

RUN id -u pmoves >/dev/null 2>&1 || useradd --create-home --shell /bin/bash pmoves
USER pmoves

CMD ["uvicorn", "nats_event_bus.app:app", "--host", "0.0.0.0", "--port", "8131"]
