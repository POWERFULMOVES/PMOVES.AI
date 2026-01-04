# PMOVES UI - Pre-built standalone image
# This Dockerfile uses pre-built Next.js standalone output from .next/standalone
# To rebuild the UI locally: cd pmoves/ui && npm run build

FROM node:20-slim

LABEL org.opencontainers.image.source="https://github.com/POWERFULMOVES/PMOVES.AI"
LABEL org.opencontainers.image.description="PMOVES.AI Unified Portal - Next.js Dashboard"

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Security: Non-root user (consistent with other PMOVES services)
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves

# Copy pre-built standalone output
COPY .next/standalone ./
COPY .next/static ./.next/static
# Note: public folder is optional - create empty if needed for static assets
RUN mkdir -p ./public

# Change ownership to non-root user
RUN chown -R pmoves:pmoves /app

USER pmoves

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:3000/api/health || exit 1

# Next.js standalone server
CMD ["node", "server.js"]
