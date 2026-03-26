module.exports = {
  daemon: true,
  run: [{
    method: "shell.run",
    params: {
      path: "../../../../pmoves",
      message: [
        "make up-agents-ui",
        "make a0-mcp-seed",
        "echo http://localhost:8081",
        "docker compose logs -f --tail=100 agent-zero"
      ],
      on: [{
        event: "/(http:\/\/[0-9.:]+)/",
        done: true
      }]
    }
  }, {
    method: "local.set",
    params: {
      url: "{{input.event[1]}}"
    }
  }]
}

