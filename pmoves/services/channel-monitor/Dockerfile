FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY channel_monitor ./channel_monitor

EXPOSE 8097

CMD ["uvicorn", "channel_monitor.main:app", "--host", "0.0.0.0", "--port", "8097"]
