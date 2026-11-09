FROM python:3.12-slim

LABEL org.opencontainers.image.title="PMOVES Model Fitness Bridge"
LABEL org.opencontainers.image.description="Subscribes to benchmark/eval events, calls model-registry fitness API"
LABEL org.opencontainers.image.source="https://github.com/POWERFULMOVES/PMOVES.AI"

RUN useradd -r -s /sbin/nologin pmoves

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER pmoves

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')" || exit 1

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
