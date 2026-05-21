FROM ubuntu:24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI (needed to invoke `docker mcp` subcommand)
RUN curl -fsSL https://get.docker.com | sh

# MCP Toolkit plugin is NOT installed here — there is no Docker daemon in a build container.
# This image is consumed by `docker mcp gateway run --profile pmoves_4090_web` on the host,
# which uses the host's own MCP Toolkit plugin. The image provides only the Docker CLI.

LABEL org.opencontainers.image.title="pmoves_4090_web" \
      org.opencontainers.image.description="PMOVES 4090 coding workstation Docker MCP profile" \
      org.opencontainers.image.source="https://github.com/POWERFULMOVES/PMOVES.AI" \
      pmoves.node="laptop-4090" \
      pmoves.profile="pmoves_4090_web"
