
FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs

EXPOSE 3000


# Install curl for healthcheck
RUN apk add --no-cache curl

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1
CMD ["npm", "start"]
