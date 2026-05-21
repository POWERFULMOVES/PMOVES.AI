FROM ubuntu:24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI (needed to invoke `docker mcp` subcommand)
RUN curl -fsSL https://get.docker.com | sh

# Install Docker MCP Toolkit plugin (graceful skip if Docker daemon not available at build time)
RUN docker plugin install docker/mcp-toolkit --grant-all-permissions 2>/dev/null || true

LABEL org.opencontainers.image.title="pmoves_4090_web" \
      org.opencontainers.image.description="PMOVES 4090 coding workstation Docker MCP profile" \
      org.opencontainers.image.source="https://github.com/POWERFULMOVES/PMOVES.AI" \
      pmoves.node="laptop-4090" \
      pmoves.profile="pmoves_4090_web"
