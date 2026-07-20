FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire service directory; the modules sit alongside main.py
# and main.py's sys.path shim makes them importable as a script-style run.
COPY __init__.py .
COPY main.py .
COPY catalog.py .
COPY transition.py .
COPY nats_pub.py .
COPY config.py .
COPY README.md .

EXPOSE 8120

# Healthcheck — service exposes GET /healthz on 8120
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8120/healthz', timeout=5)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8120"]
