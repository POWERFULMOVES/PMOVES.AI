# notebook-mcp — MCP server bridging Open Notebook REST to any MCP-consuming agent.
FROM python:3.12-slim

WORKDIR /app

# uv for fast, reproducible installs (repo pattern — see botz-gateway/ffmpeg-whisper).
# requirements.lock pins every version (direct + transitive) so a rebuild can't
# silently jump a major — e.g. mcp 2.x, which renamed FastMCP -> MCPServer and
# crash-loops this server. Regenerate the lock with: pip freeze inside the image.
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache --constraint requirements.lock -r requirements.txt

COPY server.py ./

# Streamable-HTTP MCP transport (default) binds 0.0.0.0:8092.
EXPOSE 8092

# Run as an unprivileged user (matches the hardened fleet posture).
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8092 \
    MCP_TRANSPORT=streamable-http

CMD ["python", "server.py"]
