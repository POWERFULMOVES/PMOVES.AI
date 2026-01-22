FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY supaserch/requirements.txt /tmp/requirements.txt
COPY supaserch/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

COPY . /app/services
ENV PYTHONPATH=/app
ENV SUPASERCH_PORT=8099
CMD ["uvicorn", "services.supaserch.app:app", "--host", "0.0.0.0", "--port", "8099"]
