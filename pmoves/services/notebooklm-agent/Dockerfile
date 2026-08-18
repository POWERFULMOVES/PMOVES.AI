FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY tsconfig.json ./
COPY src/ ./src/

RUN npm run build

FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/dist ./dist

# Env variables for Google OAuth
ENV GOOGLE_CLIENT_ID=""
ENV GOOGLE_CLIENT_SECRET=""
ENV GOOGLE_REFRESH_TOKEN=""

# Keep-alive PID 1 so the container stays up for the docker-exec MCP pattern.
# The MCP client runs the stdio server with attached stdin via:
#   docker exec -i pmoves-notebooklm-agent-1 node dist/index.js
# (a detached  as PID 1 would hit EOF on stdin and exit-loop.)
CMD ["tail", "-f", "/dev/null"]

# Non-root runtime (house pattern; restores #2285 intent without truncating)
RUN useradd --create-home --shell /bin/bash pmoves 2>/dev/null || true
USER pmoves
