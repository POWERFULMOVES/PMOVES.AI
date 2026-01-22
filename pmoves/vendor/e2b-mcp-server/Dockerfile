# Dockerfile for E2B MCP Server JavaScript Edition

FROM node:22-alpine AS builder

WORKDIR /app

# Copy the application files
COPY packages/js/ .

# Install dependencies
RUN npm install

# Build the application
RUN npm run build

ENV NODE_ENV=production

ENTRYPOINT ["node", "./build/index.js"]
