FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir nats-py==2.8.0
# Build context is pmoves/services; use the local copy inside this folder
COPY nats-echo/nats_echo.py /app/nats_echo.py
ENV NATS_URL=nats://nats:4222 \
    NATS_ECHO_SUBJECT=research.deepresearch.request.v1
# Let the script read NATS_URL from the environment to avoid empty-arg edge cases.
CMD ["python", "/app/nats_echo.py", "--subject", "${NATS_ECHO_SUBJECT}"]
