module.exports = {
  daemon: true,
  run: [{
    method: "fs.read",
    params: {
      path: "repo-root.txt",
      encoding: "utf8"
    }
  }, {
    method: "local.set",
    params: {
      repo_root: "{{input.trim()}}"
    }
  }, {
    method: "shell.run",
    params: {
      path: "{{path.resolve(local.repo_root, 'pmoves')}}",
      message: [
        "make up-agents-ui",
        "make a0-mcp-seed",
        "echo http://localhost:8081",
        "docker compose logs -f --tail=100 agent-zero"
      ],
      on: [{
        event: "/(http:\\/\\/[0-9.:]+)/",
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

