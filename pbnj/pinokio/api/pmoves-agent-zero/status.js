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
        "docker compose ps agent-zero",
        "py -3 -c \"import urllib.request,sys; sys.stdout.write(urllib.request.urlopen('http://localhost:8080/healthz').read().decode())\" 2>nul || echo healthz unavailable",
        "py -3 -c \"import urllib.request,sys; sys.stdout.write(urllib.request.urlopen('http://localhost:8080/mcp/commands').read().decode())\" 2>nul || echo mcp commands unavailable"
      ]
    }
  }]
}

