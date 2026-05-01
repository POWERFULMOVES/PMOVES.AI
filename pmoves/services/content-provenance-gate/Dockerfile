FROM python:3.12-slim@sha256:3d5ed973e45820f5ba5e46bd065bd88b3a504ff0724d85980dcd05eab361fcf4

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PMOVES_CONTRACTS_DIR=/app/contracts

COPY services/content-provenance-gate/requirements.in /tmp/requirements.in
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.in

COPY contracts /app/contracts
COPY services/__init__.py /app/services/__init__.py
COPY services/common /app/services/common
COPY services/content-provenance-gate /app/services/content-provenance-gate
COPY tools/chit_encode_hook.py /app/tools/chit_encode_hook.py

RUN groupadd -r pmoves --gid=65532 \
    && useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves \
    && chown -R pmoves:pmoves /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
USER pmoves:pmoves

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8112/healthz || exit 1
CMD ["uvicorn", "--app-dir", "/app/services/content-provenance-gate", "main:app", "--host", "0.0.0.0", "--port", "8112"]
