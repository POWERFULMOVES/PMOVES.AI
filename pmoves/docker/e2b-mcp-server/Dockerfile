# PMOVES.AI Hardened E2B MCP Server
# Model Context Protocol bridge for E2B sandbox integration with Agent Zero
# Clones from PMOVES fork: github.com/POWERFULMOVES/pmoves-e2b-mcp-server
# Following PMOVES.AI security standards: non-root, health checks, minimal surface

ARG NODE_VERSION=22-alpine

# =============================================================================
# Stage 1: Builder - Compile TypeScript
# =============================================================================
FROM node:${NODE_VERSION} AS builder

WORKDIR /build

# Install build dependencies
RUN apk add --no-cache \
    python3 \
    make \
    g++ \
    git

# Clone from PMOVES fork (PMOVES.AI-Edition-Hardened branch)
ARG E2B_MCP_BRANCH=PMOVES.AI-Edition-Hardened
RUN git clone --depth 1 --branch ${E2B_MCP_BRANCH} \
    https://github.com/POWERFULMOVES/pmoves-e2b-mcp-server.git \
    /build/mcp-server

WORKDIR /build/mcp-server/packages/js

# Install all dependencies (including devDependencies for build)
RUN npm ci && \
    npm run build && \
    npm prune --production

# Verify the build output
RUN test -f /build/mcp-server/packages/js/build/index.js || \
    (echo "Build failed: index.js not found" && exit 1)

# =============================================================================
# Stage 2: Runtime - Minimal Node.js Alpine
# =============================================================================
FROM node:${NODE_VERSION} AS runtime

# Labels for metadata
LABEL maintainer="PMOVES.AI <infra@pmoves.ai>" \
      description="PMOVES Hardened E2B MCP Server" \
      version="1.0.0"

# Non-root user following PMOVES.AI standards (UID 65532)
RUN addgroup -g 65532 pmoves && \
    adduser -D -u 65532 -G pmoves -s /sbin/nologin pmoves

# Runtime environment
ENV NODE_ENV=production \
    PYTHONDONTWRITEBYTECODE=1 \
    # E2B Configuration
    E2B_SANDBOX_URL=http://e2b-sandbox:7070 \
    E2B_DESKTOP_URL=http://e2b-desktop:6080 \
    # PMOVES Integration
    AGENT_ZERO_URL=http://agent-zero:8080 \
    NATS_URL=nats://nats:4222 \
    # Disable telemetry
    E2B_TELEMETRY_DISABLED=1

WORKDIR /app

# Copy built application from builder
COPY --from=builder --chown=pmoves:pmoves /build/mcp-server/packages/js/build /app/build

# Copy node_modules from builder (production only)
COPY --from=builder --chown=pmoves:pmoves /build/mcp-server/packages/js/node_modules /app/node_modules

# Copy package.json for version tracking
COPY --from=builder --chown=pmoves:pmoves /build/mcp-server/packages/js/package.json /app/

# Create writable tmp directory (noexec, nosuid for security)
RUN mkdir -p /tmp && \
    chown pmoves:pmoves /tmp

# Switch to non-root user
USER pmoves

# Expose MCP server port (HTTP API)
EXPOSE 7073

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD node -e "require('http').get('http://localhost:7073/healthz', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})" || exit 1

# Set executable permission on entrypoint
RUN chmod +x /app/build/index.js

# Run the MCP server
CMD ["node", "/app/build/index.js"]
