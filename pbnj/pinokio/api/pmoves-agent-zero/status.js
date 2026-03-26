module.exports = {
  run: [{
    method: "shell.run",
    params: {
      path: "../../../../pmoves",
      message: [
        "docker ps --format \"table {{.Names}}\t{{.Status}}\t{{.Ports}}\" | grep agent-zero || true",
        "curl -fsS http://localhost:8080/healthz || true",
        "curl -fsS http://localhost:8080/mcp/commands || true"
      ]
    }
  }]
}

