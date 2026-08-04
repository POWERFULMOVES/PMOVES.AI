ARG CUDA_VERSION=12.6.2
ARG UBUNTU_TAG=22.04

FROM nvidia/cuda:${CUDA_VERSION}-cudnn-devel-ubuntu${UBUNTU_TAG} AS ffmpeg-builder

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        ca-certificates \
        curl \
        git \
        pkg-config \
        yasm \
        nasm \
        python3 \
        python3-pip \
        python3-dev \
        libssl-dev \
        zlib1g-dev \
        libunistring-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

# whisper.cpp PINNED. This was `git clone --depth 1` with no tag, i.e. always
# upstream HEAD, and it broke the image the moment whisper.cpp gained a new
# component:
#
#   CMake Error at whisper.cpp/build/cmake_install.cmake:114 (file):
#     file INSTALL cannot find "/tmp/whisper.cpp/build/bin/libparakeet.so.1.9.1"
#
# `--target whisper` builds ONLY that target, but `cmake --install` walks the
# full install manifest, which now includes libparakeet (Parakeet ASR support).
# So the narrow build and the wide install disagreed and the layer failed.
#
# Two changes, both needed:
#   1. pin the tag — an unpinned upstream is a build that breaks on someone
#      else's release schedule, with no diff on our side to explain it
#   2. drop `--target whisper` and build the default target set, so every
#      artifact the install step expects actually exists
ARG WHISPER_CPP_REF=v1.9.1
# Baked ASR model. Defaults to large-v3 because this service's own CLAUDE.md is
# explicit: "Default: large-v3" and "PMOVES.YT batch: large-v3 always; ingest
# speed is not user-facing", alongside "NEVER silently swap models". The image
# previously baked ggml-small, which contradicted all three — and because the
# model is baked, WHISPER_MODEL could not override it at runtime.
#
# It matters most for timestamps. small is the tier where segment boundaries,
# numbers and proper nouns drift, and those segments are used as clip points
# and as quotable source, so a boundary error is a bad cut or a misquote.
# large-v3 is ~3.1GB (vs ~488MB) and fits comfortably in 16GB VRAM.
#
# Latency-bound callers (live voice agents) legitimately want small/medium —
# build them a variant with --build-arg WHISPER_GGML_MODEL=small rather than
# regressing the batch default.
ARG WHISPER_GGML_MODEL=large-v3
RUN git clone --depth 1 --branch "${WHISPER_CPP_REF}" https://github.com/ggerganov/whisper.cpp.git && \
    cmake -S whisper.cpp -B whisper.cpp/build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON \
        -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=OFF -DWHISPER_BUILD_SERVER=OFF && \
    cmake --build whisper.cpp/build --config Release && \
    cmake --install whisper.cpp/build --config Release --prefix /usr/local && \
    rm -rf whisper.cpp && \
    git clone --depth 1 https://github.com/FFmpeg/FFmpeg.git ffmpeg && \
    cd ffmpeg && \
    ./configure \
        --prefix=/opt/ffmpeg \
        --disable-debug \
        --disable-doc \
        --enable-shared \
        --enable-whisper && \
    make -j"$(nproc)" && \
    make install && \
    strip /opt/ffmpeg/bin/ffmpeg /opt/ffmpeg/bin/ffprobe && \
    mkdir -p /opt/ffmpeg/share/whisper && \
    curl -fsSL \
      "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-${WHISPER_GGML_MODEL}.bin" \
      -o "/opt/ffmpeg/share/whisper/ggml-${WHISPER_GGML_MODEL}.bin" && \
    rm -rf /tmp/ffmpeg

# Runtime image
FROM nvidia/cuda:${CUDA_VERSION}-cudnn-runtime-ubuntu${UBUNTU_TAG}

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/ffmpeg/bin:${PATH} \
    LD_LIBRARY_PATH=/usr/local/lib:/opt/ffmpeg/lib:${LD_LIBRARY_PATH} \
    WHISPER_MODEL_DIR=/opt/ffmpeg/share/whisper

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        libgomp1 \
        python3 \
        python3-pip && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ffmpeg-builder /opt/ffmpeg /opt/ffmpeg
COPY --from=ffmpeg-builder /usr/local /usr/local

WORKDIR /app

COPY pmoves/services/ffmpeg-whisper/requirements.txt ./requirements.txt
COPY pmoves/services/ffmpeg-whisper/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache-dir -r requirements.txt

COPY pmoves/services /app/services

ENV PYTHONPATH=/app

# Security: Run as non-root user (GPU services need video group)
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves -G video --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app


# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
USER pmoves:pmoves

EXPOSE 8078


# Health check (GPU service — extended start-period)
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8078/healthz || exit 1
CMD ["uvicorn","services.ffmpeg-whisper.server:app","--host","0.0.0.0","--port","8078"]
