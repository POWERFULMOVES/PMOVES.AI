FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uvicorn fastapi pydantic pydantic-settings httpx jsonschema pyyaml python-multipart referencing nats-py

COPY services/p7-room-orchestrator/ ./

RUN useradd --create-home --shell /bin/bash pmoves 2>/dev/null || true
USER pmoves

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8120"]
