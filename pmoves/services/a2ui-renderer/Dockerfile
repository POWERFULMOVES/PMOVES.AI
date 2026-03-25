FROM node:20-slim AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --ignore-scripts
COPY . .
RUN npm run build

FROM dhi.io/node:20

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
ENV PORT=8105
EXPOSE 8105

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:8105/healthz || exit 1

CMD ["node", "dist/index.js"]
