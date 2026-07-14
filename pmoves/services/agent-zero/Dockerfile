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

# Bake the PMOVES.Notes A0 plugin into the user plugins dir so it ships in the
# image (mirrors how the archon image clones its vendor via ARCHON_GIT_REF).
# It rides forward via the `COPY --from=upstream /git/agent-zero` below, and
# init-a0.sh copies /git/agent-zero/. -> /a0 at boot, so Agent Zero discovers it
# under /a0/usr/plugins/pmoves_notes. Drop the nested .git to keep the layer clean.
ARG A0_PLUGIN_PMOVES_NOTES_REMOTE=https://github.com/POWERFULMOVES/Pmoves-a0-plugin-pmoves-notes.git
ARG A0_PLUGIN_PMOVES_NOTES_REF=PMOVES.AI-Edition-Hardened
RUN git clone --depth=1 --single-branch --branch ${A0_PLUGIN_PMOVES_NOTES_REF} \
      ${A0_PLUGIN_PMOVES_NOTES_REMOTE} /git/agent-zero/usr/plugins/pmoves_notes \
    && rm -rf /git/agent-zero/usr/plugins/pmoves_notes/.git

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

# Orchestrator MCP toolkit dependencies.
# 1) docker CLI (static binary, pinned) — Agent Zero is the primary orchestrator
#    and reaches the Docker MCP toolkit (mcp/docker) over the mounted socket via
#    A0_SET_mcp_servers. Only the client binary is installed (no daemon).
# 2) @supabase/mcp-server-postgrest — pre-installed globally so the Supabase MCP
#    runs from a fixed binary instead of a runtime `npx` fetch (the agent runs on
#    a read-only rootfs; avoiding network/cache writes at startup is intentional).
ARG DOCKER_CLI_VERSION=27.5.1
ARG SUPABASE_POSTGREST_MCP_VERSION=0.1.1
RUN curl -fsSL "https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_CLI_VERSION}.tgz" \
      | tar -xz -C /usr/local/bin --strip-components=1 docker/docker \
    && docker --version \
    && npm install -g "@supabase/mcp-server-postgrest@${SUPABASE_POSTGREST_MCP_VERSION}" \
    && command -v mcp-server-postgrest

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

# PMOVES shared tools (imported by services as pmoves.tools.*)
COPY --chown=65532:65532 tools/__init__.py /app/pmoves/tools/__init__.py
COPY --chown=65532:65532 tools/chit_common.py /app/pmoves/tools/chit_common.py
COPY --chown=65532:65532 tools/chit_security.py /app/pmoves/tools/chit_security.py

# Compatibility overlay: recent flaredantic builds may omit Microsoft/notifier symbols.
# Keep Agent Zero startup resilient by overlaying a tunnel manager that degrades gracefully.
COPY --chown=65532:65532 services/agent-zero/overrides/tunnel_manager.py /git/agent-zero/python/helpers/tunnel_manager.py

USER pmoves:pmoves

EXPOSE 8080

# Health check — hits the PMOVES supervisor on :8080, not the inner AZ on :5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1
ENTRYPOINT ["/bin/bash", "-lc", \
  "/usr/local/bin/init-a0.sh 2>/dev/null || true && /opt/venv-a0/bin/python /git/agent-zero/prepare.py --dockerized=true 2>/dev/null || true && export PYTHONPATH=/app:/app/services:${PYTHONPATH:-} && exec /opt/venv-a0/bin/python /app/services/agent-zero/main.py"]
