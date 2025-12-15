FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir huggingface_hub==0.27.1

# Fetch the upstream VibeVoice sources (used by the realtime demo server).
ARG VIBEVOICE_GIT_REMOTE=https://github.com/microsoft/VibeVoice.git
ARG VIBEVOICE_GIT_REF=main
RUN git clone --depth 1 --single-branch --branch "${VIBEVOICE_GIT_REF}" "${VIBEVOICE_GIT_REMOTE}" /app/vibevoice

WORKDIR /app/vibevoice

# Apply local hardening/operational patches to upstream.
COPY services/vibevoice-realtime/patches/*.patch /tmp/patches/
RUN git apply /tmp/patches/*.patch

# Install VibeVoice (editable) so demo entrypoints import correctly.
RUN python -m pip install --no-cache-dir -e .

COPY services/vibevoice-realtime/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3000
ENTRYPOINT ["/entrypoint.sh"]
