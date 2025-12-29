FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing bytecode and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Copy and install dependencies
COPY services/session-context-worker/requirements.txt services/session-context-worker/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY services/session-context-worker /app/services/session-context-worker

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

# Expose health check port
EXPOSE 8100

# Run the application
CMD ["uvicorn", "services.session-context-worker.main:app", "--host", "0.0.0.0", "--port", "8100"]
