FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg atomicparsley ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
# Parameterize yt-dlp so we can bump independently of other deps
ARG YTDLP_VERSION=
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && if [ -n "$YTDLP_VERSION" ]; then pip install --no-cache-dir "yt-dlp[default]==${YTDLP_VERSION}"; else pip install --no-cache-dir "yt-dlp[default]"; fi
COPY . .
EXPOSE 8077
CMD ["uvicorn","yt:app","--host","0.0.0.0","--port","8077"]
