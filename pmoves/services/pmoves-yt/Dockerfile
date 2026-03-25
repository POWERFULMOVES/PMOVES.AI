# Base image pinned 2026-03-05 — refresh monthly or via Dependabot
FROM dhi.io/python:3.11
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg atomicparsley ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.lock ./
# Parameterize yt-dlp so we can bump or source from a fork
ARG YTDLP_VERSION=
ARG YTDLP_PIP_URL=
RUN pip install --no-cache-dir --upgrade pip \
    "setuptools==82.0.0" "wheel==0.46.3" \
    && pip install --no-cache-dir -r requirements.lock \
    && if [ -n "$YTDLP_PIP_URL" ]; then pip install --no-cache-dir "$YTDLP_PIP_URL"; \
       elif [ -n "$YTDLP_VERSION" ]; then pip install --no-cache-dir "yt-dlp[default]==${YTDLP_VERSION}"; \
       else pip install --no-cache-dir "yt-dlp[default]"; fi
COPY . .

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

EXPOSE 8077
CMD ["uvicorn","yt:app","--host","0.0.0.0","--port","8077"]
