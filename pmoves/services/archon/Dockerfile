FROM python:3.11-slim

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
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && corepack enable \
    && corepack prepare yarn@stable --activate \
    && corepack prepare pnpm@latest --activate \
    && rm -rf /var/lib/apt/lists/*

# Default configuration values (override at runtime)
ARG SUPABASE_URL_DEFAULT=https://your-project.supabase.co
ARG SUPABASE_SERVICE_ROLE_KEY_DEFAULT=replace-with-service-role-key
ARG SUPABASE_ANON_KEY_DEFAULT=replace-with-anon-key
ARG POSTGRES_HOST_DEFAULT=archon-postgres
ARG POSTGRES_DB_DEFAULT=postgres
ARG POSTGRES_USER_DEFAULT=postgres
ARG POSTGRES_PASSWORD_DEFAULT=postgres
ARG POSTGRES_PORT_DEFAULT=5432
ARG MCP_SERVICE_URL_DEFAULT=http://archon-mcp:8051
ARG MCP_CLIENT_ID_DEFAULT=archon
ARG MCP_CLIENT_SECRET_DEFAULT=replace-with-mcp-secret
ARG MCP_CREDENTIALS_PATH_DEFAULT=/app/config/mcp/credentials.json

ENV SUPABASE_URL=${SUPABASE_URL_DEFAULT} \
    SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_ROLE_KEY_DEFAULT} \
    SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY_DEFAULT} \
    SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY_DEFAULT} \
    POSTGRES_HOST=${POSTGRES_HOST_DEFAULT} \
    POSTGRES_PORT=${POSTGRES_PORT_DEFAULT} \
    POSTGRES_DB=${POSTGRES_DB_DEFAULT} \
    POSTGRES_USER=${POSTGRES_USER_DEFAULT} \
    POSTGRES_PASSWORD=${POSTGRES_PASSWORD_DEFAULT} \
    MCP_SERVICE_URL=${MCP_SERVICE_URL_DEFAULT} \
    MCP_CLIENT_ID=${MCP_CLIENT_ID_DEFAULT} \
    MCP_CLIENT_SECRET=${MCP_CLIENT_SECRET_DEFAULT} \
    MCP_CREDENTIALS_PATH=${MCP_CREDENTIALS_PATH_DEFAULT} \
    ARCHON_FORM=POWERFULMOVES \
    AGENT_FORMS_DIR=/app/configs/agents/forms \
    ARCHON_UI_STATIC_DIR=/app/static/archon-ui

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

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

EXPOSE 8090
CMD ["python", "services/archon/main.py"]
