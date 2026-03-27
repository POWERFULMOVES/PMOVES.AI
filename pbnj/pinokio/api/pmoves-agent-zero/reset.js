module.exports = {
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
        "docker compose stop agent-zero || echo agent-zero already stopped",
        "if exist data\\agent-zero\\runtime rmdir /s /q data\\agent-zero\\runtime",
        "if exist data\\agent-zero\\logs rmdir /s /q data\\agent-zero\\logs",
        "if not exist data\\agent-zero mkdir data\\agent-zero",
        "mkdir data\\agent-zero\\runtime",
        "mkdir data\\agent-zero\\runtime\\mcp",
        "mkdir data\\agent-zero\\logs",
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

