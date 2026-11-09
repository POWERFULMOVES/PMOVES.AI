FROM python:3.12-slim

WORKDIR /app

COPY services/p7-room-orchestrator/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/p7-room-orchestrator/ ./

RUN useradd --create-home --shell /bin/bash pmoves 2>/dev/null || true
USER pmoves

# Shell form so uvicorn honors P7_HTTP_PORT from compose; exec form would
# freeze the port at build time and ignore the runtime env.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${P7_HTTP_PORT:-8120}"]
