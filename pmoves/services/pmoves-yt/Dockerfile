# Needs apt-get for system libs (ffmpeg, atomicparsley) — cannot use DHI; pinned digest
FROM python:3.11-slim@sha256:d6e4d224f70f9e0172a06a3a2eba2f768eb146811a349278b38fff3a36463b47
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
RUN apt-get update \
    && apt-get upgrade -y \
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


# Install curl for healthcheck
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# JS runtime for YouTube player-response decoding. yt-dlp deprecated JS-less
# YouTube extraction (2026): without a runtime, format extraction fails even
# with valid cookies ("No supported JavaScript runtime could be found").
# deno is yt-dlp's default-enabled runtime. Pin via DENO_VERSION (e.g. "v2.6.4")
# for reproducible builds; "latest" tracks upstream.
ARG DENO_VERSION=latest
# TARGETARCH is supplied by BuildKit on every build. The asset name was
# hardcoded to x86_64, so the linux/arm64 leg of a multi-arch build downloaded
# an amd64 binary and died on `deno --version` with exit 127. That blocked the
# weekly yt-dlp bump build outright, and it blocks pmoves-yt on every arm64
# node -- docker-compose.arm64.override.yml pins this service to linux/arm64
# for Jetson and Spark. Unsupported arches fail loudly here rather than
# shipping an image whose JS runtime is missing.
ARG TARGETARCH
RUN set -eux;     case "${TARGETARCH}" in       amd64) deno_arch="x86_64-unknown-linux-gnu" ;;       arm64) deno_arch="aarch64-unknown-linux-gnu" ;;       *) echo "unsupported TARGETARCH='${TARGETARCH}' for deno" >&2; exit 1 ;;     esac;     if [ "$DENO_VERSION" = "latest" ]; then       url="https://github.com/denoland/deno/releases/latest/download/deno-${deno_arch}.zip";     else       url="https://github.com/denoland/deno/releases/download/${DENO_VERSION}/deno-${deno_arch}.zip";     fi;     curl -fsSL "$url" -o /tmp/deno.zip;     python -c "import zipfile,os; zipfile.ZipFile('/tmp/deno.zip').extractall('/usr/local/bin'); os.chmod('/usr/local/bin/deno',0o755)";     rm /tmp/deno.zip;     deno --version
USER pmoves:pmoves

EXPOSE 8077

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8077/healthz || exit 1
CMD ["uvicorn","yt:app","--host","0.0.0.0","--port","8077"]
