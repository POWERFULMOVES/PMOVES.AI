FROM node:24-slim AS builder

WORKDIR /app
COPY services/a2ui-renderer/package.json services/a2ui-renderer/package-lock.json* ./
RUN npm ci --ignore-scripts
COPY services/a2ui-renderer/ .
RUN npm run build

FROM node:24-slim

# Security: non-root user
RUN groupadd -r pmoves && useradd -r -g pmoves -d /app -s /sbin/nologin pmoves

# Chromium dependencies for Remotion rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    curl \
    fonts-noto-color-emoji \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder --chown=pmoves:pmoves /app/dist ./dist
COPY --from=builder --chown=pmoves:pmoves /app/node_modules ./node_modules
COPY --from=builder --chown=pmoves:pmoves /app/package.json ./

USER pmoves
ENV NODE_ENV=production
ENV PORT=8107
EXPOSE 8107

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:8107/healthz || exit 1

CMD ["node", "dist/index.js"]
