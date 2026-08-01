FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PINOKIO_BRIDGE_PORT=8130

COPY services/pinokio_bridge/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY services/pinokio_bridge /app/pinokio_bridge
COPY services/common /app/services/common

RUN id -u pmoves >/dev/null 2>&1 || useradd --create-home --shell /bin/bash pmoves
USER pmoves

CMD ["uvicorn", "pinokio_bridge.app:app", \
     "--host", "0.0.0.0", "--port", "8130"]
