FROM python:3.11-slim

WORKDIR /app

# Pinokio bridge reads ~/pinokio/ on the host — keep the container's
# home dir bind-mountable. The PINOKIO_HOME env var can override.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PINOKIO_BRIDGE_PORT=8130

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8130

# Run as the pmoves user (matches compose file's user directive)
RUN useradd --create-home --shell /bin/bash pmoves 2>/dev/null || true
USER pmoves

CMD ["python", "-m", "uvicorn", "pmoves.services.pinokio_bridge.app:app", \
     "--host", "0.0.0.0", "--port", "8130"]
