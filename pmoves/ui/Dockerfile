FROM node:20-slim AS builder

LABEL org.opencontainers.image.source="https://github.com/POWERFULMOVES/PMOVES.AI"
LABEL org.opencontainers.image.description="PMOVES.AI Unified Portal - Next.js Dashboard"

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source and build.
# NEXT_PUBLIC_* values are inlined into the browser bundle at build time —
# runtime container env cannot reach client code. Compose passes these as
# build args (the anon key is Supabase's publishable key by design). When
# absent (e.g. bare CI builds) the build still succeeds via the build-phase
# placeholders in lib/supabaseClient.ts / config/index.ts.
ARG NEXT_PUBLIC_SUPABASE_URL=
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY=
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL     NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY
COPY . .
RUN npm run build

# Production image
FROM node:20-slim AS runner
WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Security: Non-root user (consistent with other PMOVES services)
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves

# Copy built assets from builder
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

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
