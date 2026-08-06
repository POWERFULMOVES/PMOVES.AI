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

# ---------------------------------------------------------------------------
# This stage was ONE RUN: whisper.cpp build, then ffmpeg build, then a ~3.1GB
# model download. Docker caches per-RUN, so a failure in the LAST step re-ran the
# FIRST — every failed ffmpeg configure re-compiled whisper.cpp (~41 min) AND
# re-downloaded 3.1GB. That produced 39GB of build cache and contributed to a
# disk-full event that took the daemon down (2026-08-04).
#
# Now four layers, least-volatile first, so a failing configure costs a configure.
# ---------------------------------------------------------------------------

# --- Layer 1: models -------------------------------------------------------
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
#
# Baking is a FLOOR, not a claim about which model is correct: it keeps a cold or
# offline node unblocked. Model selection belongs to the catalog/registry layer
# that tracks what is current — hence the ARG and the exported env paths below.
ARG WHISPER_GGML_MODEL=large-v3
# Baked VAD model. The image previously shipped NO VAD model at all, only ASR
# weights, and af_whisper's `vad_model` has no default — so the filter could not
# segment on speech and fell back to fixed windows (see the queue note below).
# ggml-org/whisper-vad is MIT and 885,098 bytes; there was never a size reason to
# omit it.
ARG WHISPER_VAD_MODEL=silero-v5.1.2
RUN mkdir -p /opt/ffmpeg/share/whisper && \
    curl -fsSL \
      "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-${WHISPER_GGML_MODEL}.bin" \
      -o "/opt/ffmpeg/share/whisper/ggml-${WHISPER_GGML_MODEL}.bin" && \
    curl -fsSL \
      "https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-${WHISPER_VAD_MODEL}.bin" \
      -o "/opt/ffmpeg/share/whisper/ggml-${WHISPER_VAD_MODEL}.bin"

# --- Layer 2: whisper.cpp, built WITH CUDA ---------------------------------
# -DGGML_CUDA=1 is the fix for the headline defect: this image ran CPU-only on a
# CUDA base. The cmake never requested the CUDA backend, so libwhisper.so linked
# libggml-cpu alone and libggml-cuda.so was absent. af_whisper's `use_gpu`
# defaults to 1 (verified in libavfilter/af_whisper.c), so the GPU was requested
# every run and silently downgraded — ffmpeg exited 0 throughout. Measured cost:
# 2789s for 669.55s of audio = 0.24x realtime on a 4090.
#
# `=1` rather than `=ON` because that is the form whisper.cpp's own README
# documents (CMake treats both as true).
#
# The `test -f` is the point of the layer: without it a CUDA-less build succeeds
# and ships, and the failure only appears as "mysteriously slow" in production.
# Fail at build time instead.
#
# Arch list is DEPLOYMENT-TARGETED, not universal. Every additional arch is a
# full extra kernel compile baked into the image, so a "covers everything" list
# makes every node carry cubins for GPUs it will never see. Build the variant
# for the node you are deploying to.
#
# Fleet targets, from pmoves/config/profiles/*.yaml (the authoritative
# declaration, not guesswork):
#
#   x86_64 — this default:
#     86   Z890 3090Ti           CUDA 12.6.2 ok
#     89   4090 laptop           CUDA 12.6.2 ok
#
#   arm64 — set by docker-compose.arm64.override.yml build args:
#     87   Jetson Orin           REQUIRES CUDA >= 12.8 (no arm64 wheels below)
#     110  DGX Spark GB10        REQUIRES CUDA >= 12.8 (Grace-Blackwell)
#
#   not covered by any current variant:
#     120  5090 consumer Blackwell — needs CUDA >= 12.8 on x86:
#          --build-arg CUDA_VERSION=12.8.1 --build-arg CUDA_ARCHS=120
#
# Ampere cubins run on Ada (same major version) — verified empirically on the
# 4090 against an 86-only build. Do NOT assume that across major versions.
#
# VERIFY before trusting a node you have not built for. Ground truth is
#   nvidia-smi --query-gpu=compute_cap --format=csv
# on that node. The Spark value here is taken from the repo profile
# (dgx-spark-grace-blackwell.yaml: compute_capability "11.0") and has NOT been
# confirmed against hardware in this lane. A wrong arch is a silent CPU
# fallback, which is the exact failure this file already exists to prevent —
# the libggml-cuda.so guard above proves the backend was BUILT, not that its
# cubins match the GPU it lands on.
#
# Narrow to one arch when iterating (--build-arg CUDA_ARCHS=89) — it is the
# single biggest lever on build time.
ARG CUDA_ARCHS="86;89"
RUN git clone --depth 1 --branch "${WHISPER_CPP_REF}" https://github.com/ggerganov/whisper.cpp.git && \
    cmake -S whisper.cpp -B whisper.cpp/build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON \
        -DGGML_CUDA=1 -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCHS}" \
        -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=OFF -DWHISPER_BUILD_SERVER=OFF && \
    cmake --build whisper.cpp/build --config Release -j"$(nproc)" && \
    cmake --install whisper.cpp/build --config Release --prefix /usr/local && \
    test -f /usr/local/lib/libggml-cuda.so && \
    rm -rf /tmp/whisper.cpp

# --- Layer 3: ffmpeg against the CUDA-enabled whisper ----------------------
# FFmpeg PINNED for the same reason whisper.cpp is pinned above: this was
# `git clone --depth 1` on HEAD, so the larger of the two builds tracked upstream
# with no diff on our side to explain a breakage. n8.1.2 is current stable; the
# af_whisper filter this service is designed around landed in 8.0.
ARG FFMPEG_REF=n8.1.2
# configure runs `require_pkg_config whisper "whisper >= 1.7.5" ...`, and
# test_pkg_config does BOTH `pkg-config --exists` AND a compile-and-link test
# (configure lines 7398 / 1597-1610). Both failures print the same text:
#
#     ERROR: whisper >= 1.7.5 not found using pkg-config
#
# which reads like a missing package but is, once CUDA is enabled, a failing
# LINK — the generated whisper.pc does not carry the CUDA dependencies that
# libwhisper.so now has. Hence the search paths below.
#
# Deliberately NOT forcing --extra-libs="-lggml-cuda -lcudart -lcublas": with
# BUILD_SHARED_LIBS=ON the linker follows DT_NEEDED, and hardcoded library names
# are brittle (one wrong name kills configure). Add them only if the link fails.
ENV PKG_CONFIG_PATH=/usr/local/lib/pkgconfig \
    LD_LIBRARY_PATH=/usr/local/lib:/usr/local/cuda/lib64:${LD_LIBRARY_PATH}
RUN git clone --depth 1 --branch "${FFMPEG_REF}" https://github.com/FFmpeg/FFmpeg.git ffmpeg && \
    cd ffmpeg && \
    ./configure \
        --prefix=/opt/ffmpeg \
        --disable-debug \
        --disable-doc \
        --enable-shared \
        --enable-whisper \
        --extra-cflags="-I/usr/local/include" \
        --extra-ldflags="-L/usr/local/lib -L/usr/local/cuda/lib64 -L/usr/local/cuda/lib64/stubs" && \
    make -j"$(nproc)" && \
    make install && \
    strip /opt/ffmpeg/bin/ffmpeg /opt/ffmpeg/bin/ffprobe && \
    rm -rf /tmp/ffmpeg

# Runtime image
FROM nvidia/cuda:${CUDA_VERSION}-cudnn-runtime-ubuntu${UBUNTU_TAG}

# Re-declared because ARGs do not cross stages; the env below points callers at
# the baked files by path so nobody hardcodes them.
ARG WHISPER_GGML_MODEL=large-v3
ARG WHISPER_VAD_MODEL=silero-v5.1.2

# CLIP-POINT CEILING — read this before tuning VAD.
#
# af_whisper's `queue` (default 3000000us = 3s) bounds how much audio the filter
# buffers before transcribing. Without `vad_model` it is the ONLY thing that ends
# a segment, so boundaries land on fixed ~3s windows regardless of speech — the
# mechanical seams measured on this service.
#
# The trap: with `vad_model` set it STILL caps segment length. A 17s soundbite is
# unreachable under a 3s queue no matter how vad_min_silence_duration is tuned.
# Earlier A/B testing concluded "VAD barely moved the median"; queue was the
# binding constraint the whole time.
#
# For clip-point work: raise `queue` ABOVE the longest intended soundbite first,
# then tune VAD. Tuning VAD under a low queue measures nothing. e.g.
#
#   -af "whisper=model=${WHISPER_MODEL_PATH}:vad_model=${WHISPER_VAD_MODEL_PATH}\
#        :queue=30000000:vad_min_silence_duration=700000:format=srt:destination=-"
#
# Defaults verified in libavfilter/af_whisper.c at n8.1.2: queue 3000000,
# use_gpu 1, vad_threshold 0.5, vad_min_speech_duration 100000,
# vad_min_silence_duration 500000.
#
# LD_LIBRARY_PATH — do NOT add /usr/local/cuda/compat here. This base ships
# /usr/local/cuda/compat/libcuda.so.560.35.03 but leaves it off the search path,
# so ldconfig correctly resolves libcuda.so.1 to the WSL-injected shim in
# /usr/lib/x86_64-linux-gnu. Prepending the compat dir shadows that shim on
# Windows/WSL nodes: CUDA then reports "no CUDA-capable device is detected",
# falls back to CPU, and still exits 0. Verified on the 4090 against the upstream
# whisper.cpp CUDA image, which does prepend it.
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/ffmpeg/bin:${PATH} \
    LD_LIBRARY_PATH=/usr/local/lib:/opt/ffmpeg/lib:${LD_LIBRARY_PATH} \
    WHISPER_MODEL_DIR=/opt/ffmpeg/share/whisper \
    WHISPER_MODEL_PATH=/opt/ffmpeg/share/whisper/ggml-${WHISPER_GGML_MODEL}.bin \
    WHISPER_VAD_MODEL_PATH=/opt/ffmpeg/share/whisper/ggml-${WHISPER_VAD_MODEL}.bin

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
