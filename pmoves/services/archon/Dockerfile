FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System packages for builds and VCS operations
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        curl \
        ca-certificates \
        gnupg \
        libnss3 \
        libnspr4 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcups2 \
        libdrm2 \
        libgbm1 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        libxss1 \
        libxtst6 \
        libasound2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgtk-3-0 \
        fonts-liberation \
        fonts-unifont \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && corepack enable \
    && corepack prepare yarn@stable --activate \
    && corepack prepare pnpm@latest --activate \
    && rm -rf /var/lib/apt/lists/*

ARG ARCHON_GIT_REMOTE=https://github.com/POWERFULMOVES/PMOVES-Archon.git
ARG ARCHON_GIT_REF=main
ARG USE_LOCAL_VENDOR=0

# ============================================================================
# SECURITY: No default secrets in Dockerfile
# ============================================================================
# All sensitive configuration MUST be provided at runtime via:
# - docker-compose env_file directive (env.shared, .env.local)
# - docker run -e flags
# - Kubernetes ConfigMap/Secret
# - Host environment variables
#
# DO NOT add ARG defaults for:
# - API keys, tokens, passwords
# - Database credentials (POSTGRES_PASSWORD, SUPABASE_SERVICE_KEY, etc.)
# - Service secrets (MCP_CLIENT_SECRET, etc.)
# - Authentication tokens
#
# These values are intentionally NOT defined here to prevent accidental
# exposure in image layers, build cache, or docker history output.
# ============================================================================

# Non-sensitive default paths and configuration only
ENV ARCHON_FORM=POWERFULMOVES \
    AGENT_FORMS_DIR=/app/configs/agents/forms \
    ARCHON_UI_STATIC_DIR=/app/static/archon-ui \
    ARCHON_VENDOR_ROOT=/app/vendor/archon \
    MCP_CREDENTIALS_PATH=/app/config/mcp/credentials.json

# Bring in upstream Archon sources to vendor path
# Prefer local submodule when USE_LOCAL_VENDOR=1; otherwise clone from remote.
RUN if [ "${USE_LOCAL_VENDOR}" = "1" ]; then \
      echo "→ Using local submodule vendor at /app/vendor/archon"; \
      mkdir -p /app/vendor; \
      cp -R ./integrations/archon /app/vendor/archon; \
    else \
      echo "→ Cloning vendor ${ARCHON_GIT_REMOTE}@${ARCHON_GIT_REF}"; \
      git clone --depth 1 --single-branch --branch "${ARCHON_GIT_REF}" "${ARCHON_GIT_REMOTE}" /app/vendor/archon; \
    fi

# Patch upstream Archon MCP bootstrap for FastMCP compatibility.
# fastmcp>=2.x expects `instructions=` (and does not accept `description=`).
RUN set -eux; \
    target="/app/vendor/archon/python/src/mcp_server/mcp_server.py"; \
    if [ -f "$target" ] && grep -q "FastMCP(" "$target" && grep -q "description=" "$target"; then \
      sed -i '/^[[:space:]]*description=/d' "$target"; \
      echo "→ Patched MCP server description kwarg"; \
    else \
      echo "→ MCP server patch not needed"; \
    fi

COPY services/archon/requirements.txt services/archon/requirements.lock ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Pre-install Playwright browsers (Chromium) so crawl workflows succeed out of the box.
RUN python -m playwright install chromium

COPY services /app/services

# Prepare directories used at runtime
RUN mkdir -p /app/static/archon-ui /app/config/mcp

# Build the Archon UI if sources are present in the build context
ARG ARCHON_UI_DIR=archon-ui-main
ARG ARCHON_UI_BUILD_DIR=dist
RUN if [ -d "$ARCHON_UI_DIR" ]; then \
        cd "$ARCHON_UI_DIR" \
        && if [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile && pnpm build; \
           elif [ -f yarn.lock ]; then yarn install --frozen-lockfile && yarn build; \
           elif [ -f package-lock.json ]; then npm ci && npm run build; \
           else npm install && npm run build; fi \
        && mkdir -p "$ARCHON_UI_STATIC_DIR" \
        && cp -R "$ARCHON_UI_BUILD_DIR"/* "$ARCHON_UI_STATIC_DIR"/; \
    else \
        echo "Archon UI directory '$ARCHON_UI_DIR' not found. Skipping UI build."; \
    fi

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

EXPOSE 8090
CMD ["python", "-m", "services.archon.main"]
