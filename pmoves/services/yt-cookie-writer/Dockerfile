FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir httpx nats-py cryptography

COPY main.py .

RUN useradd -r -s /bin/false appuser
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD python -c "from pathlib import Path; assert Path('/tmp/healthy').exists()" || exit 1

CMD ["python", "main.py"]
