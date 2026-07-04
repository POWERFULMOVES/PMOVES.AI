module.exports = {
  run: [
    { method: "fs.read", params: { path: "repo-root.txt", encoding: "utf8" } },
    { method: "local.set", params: { repo_root: "{{input.trim()}}" } },
    { method: "shell.run", params: {
        path: "{{path.resolve(local.repo_root, 'pmoves')}}",
        message: [ "docker compose -f docker-compose.base.yml -f docker-compose.agents.yml --profile agents stop notebooklm-agent" ]
    } },
    { method: "notify", params: { html: "NotebookLM MCP agent stopped.", type: "info" } }
  ]
}
