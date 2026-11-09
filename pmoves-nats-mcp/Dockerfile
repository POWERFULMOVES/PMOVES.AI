# PMOVES NATS MCP - stdio bridge to the event bus (CORE-account + CHIT-signed publish).
# Built with uv for reproducible deps. The MCP is stdio (client-spawned); this image
# is for CI / reproducible runs and a future HTTP/SSE transport.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY nats_mcp ./nats_mcp
RUN uv sync --frozen --no-dev
# Canonical CHIT signer (pmoves.tools.chit_security) import needs the monorepo
# root on PYTHONPATH; mount it at /pmoves to enable real signing (else unsigned-local).
ENV PYTHONPATH=/pmoves
ENTRYPOINT ["uv", "run", "--no-sync", "python", "-m", "nats_mcp.server"]
