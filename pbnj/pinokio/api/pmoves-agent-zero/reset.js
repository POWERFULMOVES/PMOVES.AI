module.exports = {
  run: [{
    method: "shell.run",
    params: {
      path: "../../../../pmoves",
      message: [
        "docker compose stop agent-zero || true",
        "rm -rf data/agent-zero/runtime/* data/agent-zero/logs/*",
        "mkdir -p data/agent-zero/runtime/mcp data/agent-zero/logs",
        "make a0-mcp-seed"
      ]
    }
  }, {
    method: "notify",
    params: {
      html: "Agent Zero runtime reset complete. Start again to relaunch the service and UI.",
      type: "warning"
    }
  }]
}

