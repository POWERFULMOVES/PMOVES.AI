# PMOVES.AI Hardened E2B Surf
# Next.js web interface for agentic computer use automation
# Clones from PMOVES fork: github.com/POWERFULMOVES/pmoves-surf
# Following PMOVES.AI security standards: non-root, health checks, minimal surface

ARG NODE_VERSION=22-alpine

# =============================================================================
# Stage 1: Builder - Install dependencies and build Next.js
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
ARG E2B_SURF_BRANCH=PMOVES.AI-Edition-Hardened
RUN git clone --depth 1 --branch ${E2B_SURF_BRANCH} \
    https://github.com/POWERFULMOVES/pmoves-surf.git \
    /build/surf

WORKDIR /build/surf

# Install dependencies with pnpm (required by workspace)
# Note: package files come from cloned repo, not build context
RUN npm install -g pnpm@9.15.5 && \
    pnpm install --frozen-lockfile

# Build Next.js application
RUN pnpm build

# Verify build output
RUN test -d /build/surf/.next || \
    (echo "Build failed: .next directory not found" && exit 1)

# =============================================================================
# Stage 2: Runtime - Minimal Node.js Alpine with standalone output
# =============================================================================
FROM node:${NODE_VERSION} AS runtime

# Labels for metadata
LABEL maintainer="PMOVES.AI <infra@pmoves.ai>" \
      description="PMOVES Hardened E2B Surf - Computer Use Web Interface" \
      version="1.0.0"

# Runtime dependencies for Next.js (sharp requires native libs)
RUN apk add --no-cache \
    curl \
    openssl \
    ca-certificates

# Non-root user following PMOVES.AI standards (UID 65532)
RUN addgroup -g 65532 pmoves && \
    adduser -D -u 65532 -G pmoves -s /sbin/nologin pmoves

# Runtime environment
ENV NODE_ENV=production \
    PORT=3000 \
    # E2B Configuration
    E2B_SANDBOX_URL=http://e2b-sandbox:7070 \
    E2B_DESKTOP_URL=http://e2b-desktop:6080 \
    # Public API URL (exposed to host)
    NEXT_PUBLIC_API_URL=http://localhost:3080 \
    # Disable Next.js telemetry
    NEXT_TELEMETRY_DISABLED=1 \
    # Disable analytics in production
    VERCEL_ANALYTICS_DISABLED=1

WORKDIR /app

# Copy built application from builder
COPY --from=builder --chown=pmoves:pmoves /build/surf/.next/standalone ./
COPY --from=builder --chown=pmoves:pmoves /build/surf/.next/static ./.next/static
COPY --from=builder --chown=pmoves:pmoves /build/surf/public ./public

# Create writable cache directory (noexec, nosuid for security)
RUN mkdir -p /app/.next/cache && \
    chown pmoves:pmoves /app/.next/cache

# Switch to non-root user
USER pmoves

# Expose Next.js port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:3000/api/health || exit 1

# Run Next.js standalone server
CMD ["node", "server.js"]
