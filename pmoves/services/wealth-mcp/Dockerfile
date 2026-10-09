# wealth-mcp — MCP server bridging Firefly III REST to any MCP-consuming agent.
FROM python:3.12-slim

WORKDIR /app

# uv for fast, reproducible installs (repo pattern — see uv-cassettes skill).
# requirements.lock pins every version (direct + transitive) so a rebuild can't
# silently jump a major (e.g. mcp 2.x renamed FastMCP -> MCPServer).
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache --constraint requirements.lock -r requirements.txt

COPY server.py ./

# Streamable-HTTP MCP transport (default) binds 0.0.0.0:8092.
EXPOSE 8092

# Non-root (matches the hardened fleet posture).
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8092 \
    MCP_TRANSPORT=streamable-http

CMD ["python", "server.py"]
