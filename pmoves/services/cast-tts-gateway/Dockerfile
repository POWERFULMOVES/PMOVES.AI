FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Install catt (Cast All The Things)
RUN pip install --no-cache-dir catt[all]

# Copy application code
COPY service.py .
COPY flute_client.py .
COPY device_manager.py .

# Create non-root user
RUN useradd -m -u 65532 nonroot && \
    chown -R nonroot:nonroot /app

USER nonroot

# Expose port
EXPOSE 8060

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8060/healthz')" || exit 1

# Run service
CMD ["python", "service.py"]
