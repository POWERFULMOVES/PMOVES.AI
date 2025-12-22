FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --upgrade pip
# With build context at pmoves/ root
COPY services/common /app/services/common
COPY services/media-audio/requirements.txt ./
COPY services/media-audio/requirements.lock ./
RUN pip install --no-cache-dir --constraint requirements.lock -r requirements.txt
# services/common requires jsonschema (installed separately to avoid hash conflict)
RUN pip install --no-cache-dir jsonschema>=4.0.0
COPY services/media-audio/ ./

# Security: Run as non-root user (GPU services need video group)
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves -G video --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

EXPOSE 8082
CMD ["uvicorn","server:app","--host","0.0.0.0","--port","8082"]
