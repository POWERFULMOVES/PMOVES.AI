# Agent Zero — Elder-Melchor edition (PMOVES.AI)
#
# Base: POWERFULMOVES/PMOVES-A0-codex-docker @ PMOVES.AI-Edition-Hardened
# (Debian bookworm + Node 22 + git + bubblewrap + codex CLI). Per operator
# directive, this node's Agent Zero runs FROM the codex-docker base and gains
# host access + the PMOVES coding-agent CLIs (hermes, crush, opencode, codex)
# on top of the standard PMOVES Agent Zero runtime.
#
# The base image is NOT on GHCR yet: `make a0-elder-base` builds it from the
# PMOVES-A0-codex-docker submodule and tags it pmoves-a0-codex-base:local.
# This Dockerfile then consumes it via A0_CODEX_BASE (default below).
#
# Build context: repo root (pmoves/) — same convention as services/agent-zero.
# Usage (Known Roads only, never raw docker):
#   make a0-elder-base        # build base image from the fork submodule
#   make a0-elder-build       # build this image
#   make a0-elder-up          # build + start with the full env chain
#   make a0-elder-cli STATUS  # in-container coding-agent CLI smoke
#
# Layers:
#   1. base            — debian + node22 + codex + bubblewrap (codex-docker fork)
#   2. python + deps   — python3.11 venv + A0 fork runtime + PMOVES requirements
#   3. A0 fork         — POWERFULMOVES/PMOVES-Agent-Zero @ Hardened
#   4. plugins         — pmoves_notes + pmoves_coding_agents baked into usr/plugins
#   5. pmoves runtime  — supervisor, CHIT, contract schemas, tools overlay
#   6. coding agents   — opencode + crush + hermes (pinned installs)

ARG A0_CODEX_BASE=pmoves-a0-codex-base:local

# ── Stage 1: fetch pinned sources ───────────────────────────────
FROM debian:bookworm AS fetch

ARG AGENT_ZERO_REPO=https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git
ARG AGENT_ZERO_REF=PMOVES.AI-Edition-Hardened
ARG A0_PLUGIN_CODING_AGENTS_REMOTE=https://github.com/POWERFULMOVES/Pmoves-a0-plugin-pmoves-coding-agents.git
ARG A0_PLUGIN_PMOVES_NOTES_REMOTE=https://github.com/POWERFULMOVES/Pmoves-a0-plugin-pmoves-notes.git
ARG A0_PLUGIN_REF=PMOVES.AI-Edition-Hardened

# Cache-bust clones when branch tips move (same pattern as services/agent-zero).
ADD https://api.github.com/repos/POWERFULMOVES/PMOVES-Agent-Zero/git/ref/heads/${AGENT_ZERO_REF} /tmp/agent-zero-ref.json
ADD https://api.github.com/repos/POWERFULMOVES/Pmoves-a0-plugin-pmoves-coding-agents/git/ref/heads/${A0_PLUGIN_REF} /tmp/pm-coding-agents-ref.json
ADD https://api.github.com/repos/POWERFULMOVES/Pmoves-a0-plugin-pmoves-notes/git/ref/heads/${A0_PLUGIN_REF} /tmp/pm-notes-ref.json

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth=1 --branch ${AGENT_ZERO_REF} ${AGENT_ZERO_REPO} /git/agent-zero \
    && rm -rf /git/agent-zero/.git

RUN git clone --depth=1 --single-branch --branch ${A0_PLUGIN_REF} \
      ${A0_PLUGIN_CODING_AGENTS_REMOTE} /git/agent-zero/usr/plugins/pmoves_coding_agents \
    && rm -rf /git/agent-zero/usr/plugins/pmoves_coding_agents/.git

RUN git clone --depth=1 --single-branch --branch ${A0_PLUGIN_REF} \
      ${A0_PLUGIN_PMOVES_NOTES_REMOTE} /git/agent-zero/usr/plugins/pmoves_notes \
    && rm -rf /git/agent-zero/usr/plugins/pmoves_notes/.git

# ── Stage 2: PMOVES runtime on the codex-docker base ────────────
FROM ${A0_CODEX_BASE} AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app:/app/services" \
    AGENT_ZERO_HOME=/a0 \
    AGENT_ZERO_ROOT=/a0 \
    PMOVES_WORKSPACE=/workspace

WORKDIR /app

# Runtime user (mirrors services/agent-zero hardening).
RUN groupadd -r pmoves --gid=65532 \
    && useradd -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves \
    && install -d -o 65532 -g 65532 /a0 /workspace \
    && chown 65532:65532 /app

# System deps for the A0 runtime (no apt python — see uv note below).
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      ffmpeg tesseract-ocr poppler-utils libgl1 libglib2.0-0 libsm6 libxext6 \
      ca-certificates curl git bubblewrap procps \
    && rm -rf /var/lib/apt/lists/*

# Python: uv-managed CPython 3.12, NOT apt python3.11. The A0 fork @ Hardened
# uses PEP 695 type aliases (helpers/subagents.py: `type Origin = ...`) which
# are 3.12+ syntax — 3.11 dies at import with SyntaxError (observed live
# 2026-09-08). uv fetches a standalone CPython into the image.
COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /uvx /usr/local/bin/
# UV_PYTHON_INSTALL_DIR must point OUTSIDE /root: uv's default managed-python
# home is $HOME/.local/share/uv/python, and build-layer $HOME is /root (mode
# 700) — the venv interpreter symlinks into it, so the runtime user (65532)
# got "Permission denied" on exec (live 2026-09-08, crash-loop exit 126).
ENV UV_PYTHON_INSTALL_DIR=/usr/local/share/uv-python
RUN uv venv /opt/venv-a0 --python 3.12 \
    && chmod -R a+rX /usr/local/share/uv-python /opt/venv-a0
ENV PATH="/opt/venv-a0/bin:${PATH}"

# A0 fork tree + baked plugins (from fetch stage) — before dep install so the
# fork's requirements.txt is available to install from.
COPY --from=fetch --chown=65532:65532 /git/agent-zero /git/agent-zero

# Python deps: upstream A0 runtime (with PMOVES constraints), then PMOVES
# wrapper requirements locked (same two-step contract as services/agent-zero).
COPY services/agent-zero/upstream-constraints.txt /tmp/upstream-constraints.txt
COPY services/agent-zero/requirements.txt services/agent-zero/requirements.lock ./
RUN uv pip install --python /opt/venv-a0/bin/python --no-cache-dir \
       --constraint /tmp/upstream-constraints.txt \
       -r /git/agent-zero/requirements.txt \
    && if [ -f /git/agent-zero/requirements2.txt ]; then \
         uv pip install --python /opt/venv-a0/bin/python --no-cache-dir \
           --constraint /tmp/upstream-constraints.txt \
           -r /git/agent-zero/requirements2.txt; \
       fi \
    && uv pip install --python /opt/venv-a0/bin/python --no-cache-dir \
       --constraint requirements.lock -r requirements.txt

# PMOVES supervisor + runtime assets (same layout as services/agent-zero).
COPY --chown=65532:65532 services ${AGENT_ZERO_HOME}/../app/services
COPY --chown=65532:65532 services/agent-zero/runtime ${AGENT_ZERO_HOME}/runtime
# Compatibility overlay (flaredantic missing-symbol guard, see agent-zero image).
COPY --chown=65532:65532 services/agent-zero/overrides/tunnel_manager.py /git/agent-zero/helpers/tunnel_manager.py

# PMOVES namespace: CHIT + shared tools (minimal namespace init, as agent-zero).
RUN install -d -o 65532 -g 65532 /app/pmoves /app/pmoves/tools \
    && printf '"""Minimal pmoves namespace for Docker."""\n' > /app/pmoves/__init__.py \
    && chown 65532:65532 /app/pmoves/__init__.py
COPY --chown=65532:65532 chit /app/pmoves/chit
COPY --chown=65532:65532 contracts /app/contracts
COPY --chown=65532:65532 configs /app/configs
COPY --chown=65532:65532 tools/__init__.py /app/pmoves/tools/__init__.py
COPY --chown=65532:65532 tools/chit_common.py /app/pmoves/tools/chit_common.py
COPY --chown=65532:65532 tools/chit_security.py /app/pmoves/tools/chit_security.py

# Init script (replaces upstream /ins/copy_A0.sh — stock copy contract, plus
# the env-driven _model_config presets generation; see the script header).
COPY --chown=65532:65532 services/a0-elder-melchor/init-a0.sh /usr/local/bin/init-a0.sh
RUN chmod +x /usr/local/bin/init-a0.sh

# Host-mounted workspace (/workspace carries the PMOVES.AI repo from the host)
# reads as foreign-owned to git → "dubious ownership" refusals in every CLI.
RUN git config --system --add safe.directory '*'

# ── Coding-agent CLIs (the point of this edition) ────────────────
# codex ships in the base image. Pins follow PMOVES-registry manifests
# (opencode/agent.json) and the fleet winget pin (crush 0.92.0); hermes-agent
# follows the fleet Hermes profile version. Bump pins via PR only.
# hermes gets its OWN venv: hermes-agent installs a top-level `plugins`
# package into site-packages ("Hermes plugins") which SHADOWS Agent Zero's
# /a0/plugins namespace dir — regular packages beat namespace dirs on any
# sys.path order, and the inner A0 runtime died with
# `ModuleNotFoundError: No module named 'plugins._model_config'` (live
# 2026-09-08). /usr/local/bin/hermes symlinks into the isolated venv.
ARG OPENCODE_VERSION=1.18.29
ARG CRUSH_VERSION=0.92.0
ARG HERMES_AGENT_VERSION=0.19.0
RUN npm install -g "opencode-ai@${OPENCODE_VERSION}" \
    && curl -fsSL "https://github.com/charmbracelet/crush/releases/download/v${CRUSH_VERSION}/crush_${CRUSH_VERSION}_Linux_x86_64.tar.gz" \
       | tar -xz -C /usr/local/bin --strip-components=1 "crush_${CRUSH_VERSION}_Linux_x86_64/crush" \
    && uv venv /opt/venv-hermes --python 3.12 \
    && uv pip install --python /opt/venv-hermes/bin/python --no-cache-dir "hermes-agent==${HERMES_AGENT_VERSION}" \
    && ln -s /opt/venv-hermes/bin/hermes /usr/local/bin/hermes \
    && for cli in codex opencode crush hermes; do printf '%-10s %s\n' "$cli" "$(command -v $cli)"; done

USER pmoves:pmoves

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

ENTRYPOINT ["/bin/bash", "-lc", \
  "/usr/local/bin/init-a0.sh 2>/dev/null || true && /opt/venv-a0/bin/python /git/agent-zero/prepare.py --dockerized=true 2>/dev/null || true && export PYTHONPATH=/app:/app/services:${PYTHONPATH:-} && exec /opt/venv-a0/bin/python /app/services/agent-zero/main.py"]
