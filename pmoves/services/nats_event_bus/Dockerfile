FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NATS_EVENT_BUS_PORT=8131

COPY services/nats_event_bus/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY services/nats_event_bus /app/nats_event_bus
COPY services/common /app/services/common

RUN useradd --create-home --shell /bin/bash pmoves 2>/dev/null || true
USER pmoves

CMD ["uvicorn", "nats_event_bus.app:app", "--host", "0.0.0.0", "--port", "8131"]
