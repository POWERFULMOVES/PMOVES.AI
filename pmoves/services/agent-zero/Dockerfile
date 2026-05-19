# Build context: repo root (pmoves/)
# Usage: docker build -f services/agent-zero/Dockerfile -t pmoves-agent-zero:latest .
#
# Uses agent-zero-base (Debian, not Kali) — matches Dockerfile.multiarch pattern.
# Refresh A0_BASE_TAG monthly or via Dependabot.

# ── Stage 1: Build upstream Agent Zero ──────────────────────────
ARG A0_BASE_TAG=latest
FROM agent0ai/agent-zero-base:${A0_BASE_TAG} AS upstream

ARG AGENT_ZERO_REPO=https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git
ARG AGENT_ZERO_REF=PMOVES.AI-Edition-Hardened

# Clone PMOVES fork of Agent Zero (matches submodule branch)
RUN git clone --depth=1 --branch ${AGENT_ZERO_REF} \
      ${AGENT_ZERO_REPO} /git/agent-zero

# Minimal constraints for upstream transitive deps that have broken releases.
# Do NOT use requirements.lock here — it pins our direct deps and will
# conflict with upstream version requirements (e.g. crontab version mismatch).
COPY services/agent-zero/upstream-constraints.txt /tmp/upstream-constraints.txt

# Install upstream deps into the pre-existing /opt/venv-a0.
# NOTE: preload.py intentionally NOT run. PMOVES routes embeddings through
# TensorZero (A0_SET_embed_model_provider=openai), not HuggingFace.
# The preload downloads ~80MB sentence-transformers model never used at runtime.
# If re-enabling, also add huggingface.co:443 to integrations-ghcr.yml egress.
RUN . /opt/venv-a0/bin/activate \
    && uv pip install --no-cache-dir --constraint /tmp/upstream-constraints.txt -r /git/agent-zero/requirements.txt \
    && uv pip install --no-cache-dir --constraint /tmp/upstream-constraints.txt -r /git/agent-zero/requirements2.txt

# ── Stage 2: PMOVES overlay ────────────────────────────────────
FROM agent0ai/agent-zero-base:${A0_BASE_TAG} AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app:/app/services" \
    AGENT_ZERO_HOME=/a0 \
    AGENT_ZERO_ROOT=/a0 \
    PATH="/opt/venv-a0/bin:${PATH}"

WORKDIR /app

# Create the runtime user before COPY steps so we can preserve ownership as
# files enter the image instead of paying for a large recursive chown later.
RUN groupadd -r pmoves --gid=65532 \
    && useradd -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves \
    && install -d -o 65532 -g 65532 /a0 \
    && chown 65532:65532 /app

# Bring in upstream runtime from builder stage
COPY --from=upstream --chown=65532:65532 /opt/venv-a0 /opt/venv-a0
COPY --from=upstream --chown=65532:65532 /git/agent-zero /git/agent-zero

# System deps required by Agent Zero upstream runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential python3-dev ffmpeg tesseract-ocr poppler-utils \
      libgl1 libglib2.0-0 libsm6 libxext6 curl \
    && rm -rf /var/lib/apt/lists/*

# PMOVES Python requirements (overrides upstream pins where needed)
COPY --chown=65532:65532 services/agent-zero/requirements.txt services/agent-zero/requirements.lock ./
RUN . /opt/venv-a0/bin/activate \
    && uv pip install --no-cache-dir \
       --constraint requirements.lock -r requirements.txt

# Init script (replaces upstream /ins/copy_A0.sh)
RUN install -d -o 65532 -g 65532 /a0 \
    && printf '#!/bin/bash\nset -e\nif [ ! -f "/a0/run_ui.py" ]; then\n  cp -rn --no-preserve=ownership,mode "/git/agent-zero/." "/a0"\nfi\n' \
       > /usr/local/bin/init-a0.sh \
    && chmod +x /usr/local/bin/init-a0.sh

# PMOVES runtime assets
COPY --chown=65532:65532 services/agent-zero/runtime ${AGENT_ZERO_HOME}/runtime

# PMOVES Python namespace package (for `from pmoves.chit import ...`)
# Generate a minimal __init__.py instead of copying the repo's version,
# which imports pmoves.services — a path that doesn't exist in the Docker layout.
RUN install -d -o 65532 -g 65532 /app/pmoves \
    && printf '"""Minimal pmoves namespace for Docker."""\n' > /app/pmoves/__init__.py \
    && chown 65532:65532 /app/pmoves/__init__.py
COPY --chown=65532:65532 chit /app/pmoves/chit

# PMOVES contract schemas + agent forms
COPY --chown=65532:65532 contracts /app/contracts
COPY --chown=65532:65532 configs /app/configs

# PMOVES services (includes services/common, services/agent_zero, etc.)
COPY --chown=65532:65532 services /app/services

# Compatibility overlay: recent flaredantic builds may omit Microsoft/notifier symbols.
# Keep Agent Zero startup resilient by overlaying a tunnel manager that degrades gracefully.
COPY --chown=65532:65532 services/agent-zero/overrides/tunnel_manager.py /git/agent-zero/python/helpers/tunnel_manager.py

USER pmoves:pmoves

EXPOSE 8080

# Health check — hits the PMOVES supervisor on :8080, not the inner AZ on :5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1
ENTRYPOINT ["/bin/bash", "-lc", \
  "/usr/local/bin/init-a0.sh 2>/dev/null || true && if [ \"$(id -u)\" = \"0\" ]; then /opt/venv-a0/bin/python /git/agent-zero/prepare.py --dockerized=true 2>/dev/null || true; fi && export PYTHONPATH=/app:/app/services:${PYTHONPATH:-} && exec /opt/venv-a0/bin/python /app/services/agent-zero/main.py"]
