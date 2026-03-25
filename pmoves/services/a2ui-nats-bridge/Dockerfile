FROM python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY bridge.py .

# Create non-root user
RUN useradd -m -u 1001 pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves

EXPOSE 9224

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9224/healthz')"

CMD ["python", "bridge.py"]
