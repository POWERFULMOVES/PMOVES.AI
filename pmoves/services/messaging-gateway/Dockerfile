FROM python:3.11-slim@sha256:ce81dc539f0aedc9114cae640f8352fad83d37461c24a3615b01f081d0c0f434

WORKDIR /app

# Create non-root user with explicit UID for security
RUN useradd --create-home --shell /bin/bash --uid 1001 pmoves

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Change ownership to non-root user
RUN chown -R pmoves:pmoves /app

# Switch to non-root user
USER 1001

ENV PORT=8101
EXPOSE 8101

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8101/healthz || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8101"]
