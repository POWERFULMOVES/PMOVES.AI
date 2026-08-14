FROM python:3.12-slim

WORKDIR /app

COPY services/p7-room-orchestrator/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/p7-room-orchestrator/ ./

RUN useradd --create-home --shell /bin/bash pmoves 2>/dev/null || true
USER pmoves

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8120"]
