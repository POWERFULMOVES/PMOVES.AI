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

RUN git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git && \
    cmake -S whisper.cpp -B whisper.cpp/build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON \
        -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=OFF -DWHISPER_BUILD_SERVER=OFF && \
    cmake --build whisper.cpp/build --config Release --target whisper && \
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
      https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin \
      -o /opt/ffmpeg/share/whisper/ggml-small.bin && \
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

USER pmoves:pmoves

EXPOSE 8078

CMD ["uvicorn","services.ffmpeg-whisper.server:app","--host","0.0.0.0","--port","8078"]
