FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/POWERFULMOVES/PMOVES.AI"
LABEL org.opencontainers.image.description="PMOVES-BoTZ Gateway - Work item coordination service"

WORKDIR /app

# Install dependencies
COPY requirements.txt requirements.lock .
RUN pip install --no-cache-dir --constraint requirements.lock -r requirements.txt

# Copy application
COPY main.py .

# Create non-root user
RUN useradd -r -u 1000 pmoves && chown -R pmoves:pmoves /app
USER pmoves

EXPOSE 8054

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8054/healthz', timeout=5)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8054"]
