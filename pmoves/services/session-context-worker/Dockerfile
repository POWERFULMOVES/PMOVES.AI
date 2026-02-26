FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY services/session-context-worker/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.lock

COPY services/session-context-worker /app/services/session-context-worker

# Security: run as non-root.
RUN groupadd -r pmoves --gid=65532 \
    && useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves \
    && chown -R pmoves:pmoves /app

USER pmoves:pmoves
CMD ["uvicorn", "--app-dir", "/app/services/session-context-worker", "main:app", "--host", "0.0.0.0", "--port", "8100"]
