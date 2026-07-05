// Launch the NotebookLM MCP agent through the CANONICAL make pipeline:
//   (1) make secrets-funnel   (2) make up-notebooklm  (= $(DC) --profile agents up -d --build)
// $(DC) injects COMPOSE_ENV_FILES/tier env files — never raw `docker compose up`.
// It's a stdio MCP server (no web URL); the MCP client reaches it via docker exec
// per pmoves/config/mcp/notebooklm-agent.yaml.
module.exports = {
  run: [
    { method: "fs.read", params: { path: "repo-root.txt", encoding: "utf8" } },
    { method: "local.set", params: { repo_root: "{{input.trim()}}" } },
    { method: "shell.run", params: {
        path: "{{path.resolve(local.repo_root, 'pmoves')}}",
        message: [ "make secrets-funnel", "make up-notebooklm" ]
    } },
    { method: "notify", params: { html: "NotebookLM MCP agent up (detached, stdio via docker exec). Set GOOGLE_REFRESH_TOKEN in env.shared for live queries.", type: "success" } }
  ]
}
