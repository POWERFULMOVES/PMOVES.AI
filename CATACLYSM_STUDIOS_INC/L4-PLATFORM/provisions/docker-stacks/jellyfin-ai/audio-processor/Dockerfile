FROM python:3.11-slim AS ffmpeg-downloader

ARG FFMPEG_VERSION=7.1
ARG FFMPEG_ARCHIVE=ffmpeg-n${FFMPEG_VERSION}-latest-linux64-gpl-${FFMPEG_VERSION}.tar.xz
ARG FFMPEG_ARCHIVE_DIR=ffmpeg-n${FFMPEG_VERSION}-latest-linux64-gpl-${FFMPEG_VERSION}

ENV DEBIAN_FRONTEND=noninteractive

# Download the pinned FFmpeg 7.1 build with HDR/AV1/NVENC/VAAPI support
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/${FFMPEG_ARCHIVE}" -o /tmp/ffmpeg.tar.xz \
    && mkdir -p /opt \
    && tar -xJf /tmp/ffmpeg.tar.xz -C /opt \
    && mv /opt/${FFMPEG_ARCHIVE_DIR} /opt/ffmpeg \
    && rm -f /tmp/ffmpeg.tar.xz

FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/opt/ffmpeg/bin:${PATH}"

WORKDIR /app

# Runtime dependencies required for audio processing and GPU detection utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libasound2 \
    libdrm2 \
    libsndfile1 \
    libva2 \
    libva-drm2 \
    libva-x11-2 \
    libvdpau1 \
    ocl-icd-libopencl1 \
    vainfo \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ffmpeg-downloader /opt/ffmpeg /opt/ffmpeg

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories and a runtime account to own them.
# python:slim ships no unprivileged user, so one is made here. A fixed high uid
# keeps ownership stable across rebuilds and matches bind-mounted host paths
# predictably.
RUN useradd --system --create-home --uid 10001 appuser     && mkdir -p /app/logs /app/output /app/temp     && chown -R appuser:appuser /app

# Set permissions
RUN chmod +x /app/entrypoint.sh

EXPOSE 8001

# Drop root. 8001 is unprivileged and every write target above is owned by
# appuser; ffmpeg in /opt is read-only at runtime.
USER appuser

CMD ["./entrypoint.sh"]
