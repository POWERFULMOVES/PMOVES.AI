# notebook-mcp — MCP server bridging Open Notebook REST to any MCP-consuming agent.
FROM python:3.12-slim

WORKDIR /app

# deps first for layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

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
