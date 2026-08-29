
FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy application code
COPY . .

# Create necessary directories, owned by the runtime user.
# node:alpine already ships an unprivileged `node` account (uid 1000); the app
# only needs to write /app/logs, so chown that rather than the whole tree.
RUN mkdir -p /app/logs && chown -R node:node /app/logs

EXPOSE 3000

# Drop root. Nothing here binds a privileged port (3000) or writes outside /app.
USER node

CMD ["npm", "start"]
