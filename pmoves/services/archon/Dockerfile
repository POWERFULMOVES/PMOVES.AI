# PMOVES Archon - Supabase-driven Agent Service with MCP Integration
# Multi-stage hardened build following PMOVES.AI security standards
#
# This service integrates the upstream POWERFULMOVES/PMOVES-Archon project
# with PMOVES infrastructure, including FastMCP compatibility patches.

ARG PYTHON_BASE=python:3.12-slim

# ===== Stage 1: Python Builder =====
FROM ${PYTHON_BASE}@sha256:9e01bf1ae5db7649a236da7be1e94ffbbbdd7a93f867dd0d8d5720d9e1f89fab AS python-builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
# NOTE: requirements.txt includes Playwright which needs build tools
COPY services/archon/requirements.txt services/archon/requirements.lock .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt --target /install

# ===== Stage 2: Node.js UI Builder =====
FROM ${PYTHON_BASE}@sha256:9e01bf1ae5db7649a236da7be1e94ffbbbdd7a93f867dd0d8d5720d9e1f89fab AS ui-builder

# Install Node.js and UI build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && corepack enable \
    && corepack prepare yarn@stable --activate \
    && corepack prepare pnpm@latest --activate \
    && rm -rf /var/lib/apt/lists/*

# Build arguments for UI
ARG ARCHON_UI_DIR=archon-ui-main
ARG ARCHON_UI_BUILD_DIR=dist

# Create empty UI directories (optional build will use these if sources exist)
RUN mkdir -p /ui-src /ui-build

# Copy UI sources if present - using a wildcard pattern that works even if directory doesn't exist
# The build context must include this directory, or this step will create an empty /ui-src

# Build the UI (if sources exist)
RUN if [ -f /ui-src/pnpm-lock.yaml ]; then \
        cd /ui-src && pnpm install --frozen-lockfile && pnpm build; \
    elif [ -f /ui-src/yarn.lock ]; then \
        cd /ui-src && yarn install --frozen-lockfile && yarn build; \
    elif [ -f /ui-src/package-lock.json ]; then \
        cd /ui-src && npm ci && npm run build; \
    else \
        mkdir -p /ui-build; \
        echo "No UI sources found, skipping build"; \
    fi

# Prepare UI artifacts for final stage
RUN mkdir -p /ui-build && \
    if [ -d "/ui-src/${ARCHON_UI_BUILD_DIR}" ]; then \
        cp -R "/ui-src/${ARCHON_UI_BUILD_DIR}"/* /ui-build/; \
    fi

# ===== Stage 3: Archon Vendor Builder =====
FROM ${PYTHON_BASE}@sha256:9e01bf1ae5db7649a236da7be1e94ffbbbdd7a93f867dd0d8d5720d9e1f89fab AS vendor-builder

ARG ARCHON_GIT_REMOTE=https://github.com/POWERFULMOVES/PMOVES-Archon.git
ARG ARCHON_GIT_REF=main
ARG USE_LOCAL_VENDOR=0

WORKDIR /build

# Install git for cloning
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Copy local vendor submodule (if provided)
COPY integrations/archon /app/_local_vendor/archon

# Clone or copy Archon sources
RUN if [ "${USE_LOCAL_VENDOR}" = "1" ]; then \
        mkdir -p /app/vendor && \
        cp -R /app/_local_vendor/archon /app/vendor/archon; \
    else \
        git clone --depth 1 --single-branch --branch "${ARCHON_GIT_REF}" \
            "${ARCHON_GIT_REMOTE}" /app/vendor/archon; \
    fi

# Patch upstream Archon MCP bootstrap for FastMCP compatibility
# fastmcp>=2.x expects `instructions=` (not `description=`)
RUN set -eux; \
    target="/app/vendor/archon/python/src/mcp_server/mcp_server.py"; \
    if [ -f "$target" ] && grep -q "FastMCP(" "$target" && grep -q "description=" "$target"; then \
        sed -i '/^[[:space:]]*description=/d' "$target"; \
        echo "→ Patched MCP server description kwarg"; \
    fi

# Patch upstream Archon migration checker to avoid `/rpc/sql` calls
RUN python3 <<'PY'
from __future__ import annotations
import re
from pathlib import Path

path = Path("/app/vendor/archon/python/src/server/services/migration_service.py")
if not path.exists():
    raise SystemExit(0)

text = path.read_text(encoding="utf-8")
marker = "async def check_migrations_table_exists"
start = text.find(marker)
if start == -1:
    raise SystemExit(0)

match = re.search(r"\n    async def [a-zA-Z_][a-zA-Z0-9_]*\(", text[start + 1 :])
end = (start + 1 + match.start()) if match else len(text)

replacement = """async def check_migrations_table_exists(self) -> bool:
    \"\"\"
    Check if the archon_migrations table exists in the database.
    Supabase REST does not include a built-in `sql` RPC endpoint.
    \"\"\"
    supabase = self._get_supabase_client()
    try:
        supabase.table("archon_migrations").select("id").limit(0).execute()
        return True
    except Exception:
        return False

"""

patched = text[:start] + replacement + text[end:]
path.write_text(patched, encoding="utf-8")
print("→ Patched Archon check_migrations_table_exists")
PY

# ===== Stage 4: Runtime =====
FROM ${PYTHON_BASE}@sha256:9e01bf1ae5db7649a236da7be1e94ffbbbdd7a93f867dd0d8d5720d9e1f89fab

# Metadata labels
LABEL maintainer="PMOVES.AI <infra@pmoves.ai>" \
      org.opencontainers.image.title="PMOVES Archon" \
      org.opencontainers.image.description="Supabase-driven agent service with MCP integration" \
      org.opencontainers.image.vendor="PMOVES.AI" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/powerfulmoves/PMOVES-Archon" \
      pmoves.upstream.repo="https://github.com/POWERFULMOVES/PMOVES-Archon.git"

# Runtime environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    ARCHON_FORM=POWERFULMOVES \
    AGENT_FORMS_DIR=/app/configs/agents/forms \
    ARCHON_UI_STATIC_DIR=/app/static/archon-ui \
    ARCHON_VENDOR_ROOT=/app/vendor/archon \
    MCP_CREDENTIALS_PATH=/app/config/mcp/credentials.json

WORKDIR /app

# Install runtime dependencies (minimal - only what's needed for Playwright browser ops)
# Note: We keep the GTK/ATK libraries for Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
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
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder
COPY --from=python-builder /install /usr/local

# Copy Archon vendor (with patches applied)
COPY --from=vendor-builder /app/vendor/archon /app/vendor/archon

# Copy UI build artifacts (if any)
COPY --from=ui-builder /ui-build /app/static/archon-ui

# Copy application code
COPY services /app/services

# Prepare directories
RUN mkdir -p /app/config/mcp /app/configs/agents/forms /app/static/archon-ui

# Pre-install Playwright browsers (Chromium)
# Note: patchright is the Playwright fork we use
RUN python -m patchright install --with-deps chromium || \
    python -m playwright install --with-deps chromium || true

# Security: Create non-root user with PMOVES standard UID/GID
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

# Health check endpoint for orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8091/healthz || exit 1

EXPOSE 8091

CMD ["python", "-m", "services.archon.main"]
