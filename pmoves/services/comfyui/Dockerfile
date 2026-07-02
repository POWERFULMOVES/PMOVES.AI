# ComfyUI — self-host build (replaces the vendor `runpod/comfyui` image).
#
# Why build-from-source: PMOVES.AI runs ComfyUI on its OWN fleet GPUs (5090 /
# Spark), not RunPod. Building from the upstream repo on a license-clean base
# keeps the runtime reproducible and removes the vendor dependency.
#
# Licenses: ComfyUI is GPL-3.0 (self-host / internal use is fine); the PyTorch
# base is BSD-3-Clause; CUDA runtime is under NVIDIA's redistributable terms.
# No CC-BY-NC anywhere — consistent with the creator-pipeline license gate.
#
# GPU IMAGE — must be built and smoke-validated ON-NODE (5090 amd64 / Spark
# arm64) before fleet rollout; CI does not build GPU images. Same pattern as the
# OmniVoice deploy unit (#1845).

ARG TORCH_BASE=pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
FROM ${TORCH_BASE}

# Pin ComfyUI to a verified release tag. Bump deliberately and re-validate the
# build on-node — never track a moving branch (reproducibility).
ARG COMFYUI_REF=v0.3.40
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    COMFYUI_REF=${COMFYUI_REF}

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --depth 1 --branch "${COMFYUI_REF}" \
        https://github.com/comfyanonymous/ComfyUI.git \
    && cd ComfyUI \
    && pip install --no-cache-dir -r requirements.txt

WORKDIR /opt/ComfyUI

# Persistent surfaces. IMPORTANT: mount named volumes / binds at these SUBPATHS,
# never at /opt/ComfyUI itself — a volume over the app dir would hide the baked
# source. Pre-create so an empty volume mount keeps correct ownership.
RUN mkdir -p models output input custom_nodes user

# Non-root (matches the 65532 fleet convention used across pmoves services).
RUN groupadd -r pmoves --gid=65532 \
    && useradd -r -g pmoves --uid=65532 --home-dir=/opt/ComfyUI --shell=/sbin/nologin pmoves \
    && chown -R pmoves:pmoves /opt/ComfyUI
USER pmoves:pmoves

EXPOSE 8188

# ComfyUI serves its UI/root on :8188 once the model graph is ready.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS http://localhost:8188/ >/dev/null || exit 1

CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188"]
