FROM python:3.11-slim

WORKDIR /app

# Build context is the monorepo root (matching the existing
# `context: .` in docker-compose.yml / docker-compose.agents.yml), so all
# COPY paths are relative to that root.
COPY services/p7-room-orchestrator/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Service modules. main.py's sys.path shim makes them importable as a
# script-style run from /app; this matches how uvicorn is launched below.
COPY services/p7-room-orchestrator/__init__.py   ./__init__.py
COPY services/p7-room-orchestrator/main.py        ./main.py
COPY services/p7-room-orchestrator/catalog.py     ./catalog.py
COPY services/p7-room-orchestrator/transition.py  ./transition.py
COPY services/p7-room-orchestrator/nats_pub.py    ./nats_pub.py
COPY services/p7-room-orchestrator/config.py      ./config.py
COPY services/p7-room-orchestrator/README.md      ./README.md

EXPOSE 8120

# Bind to 0.0.0.0 inside the container so container-published ports work
# (the host bind is constrained by P7_BIND in docker-compose.yml).
ENV P7_HOST=0.0.0.0

# Healthcheck — service exposes GET /healthz on 8120.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8120/healthz', timeout=5)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8120"]
