// Bring up the NotebookLM MCP agent (compose profile: agents). It's a stdio MCP
// server (no URL) — the MCP client reaches it via `docker exec` per
// pmoves/config/mcp/notebooklm-agent.yaml. Streams logs as a daemon.
// Requires the base networks (pmoves_app, pmoves_external) to already exist.
module.exports = {
  daemon: true,
  run: [
    { method: "fs.read", params: { path: "repo-root.txt", encoding: "utf8" } },
    { method: "local.set", params: { repo_root: "{{input.trim()}}" } },
    { method: "shell.run", params: {
        path: "{{path.resolve(local.repo_root, 'pmoves')}}",
        message: [
          "docker compose -f docker-compose.base.yml -f docker-compose.agents.yml --profile agents up -d notebooklm-agent",
          "echo NotebookLM MCP agent is up (stdio via docker exec). Set GOOGLE_REFRESH_TOKEN for live queries.",
          "docker compose -f docker-compose.base.yml -f docker-compose.agents.yml logs -f --tail=100 notebooklm-agent"
        ]
    } }
  ]
}
