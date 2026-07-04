// Build the NotebookLM MCP agent image (multi-stage; npm ci + tsc). Picks the
// PMOVES.AI repo root once and remembers it, mirroring the other pmoves-* launchers.
module.exports = {
  run: [
    { method: "filepicker.open", params: { title: "Select PMOVES.AI repository root", type: "folder" } },
    { method: "local.set", params: { repo_root: "{{input.paths[0]}}" } },
    { method: "fs.write", params: { path: "repo-root.txt", text: "{{local.repo_root}}" } },
    { method: "shell.run", params: {
        path: "{{path.resolve(local.repo_root, 'pmoves')}}",
        message: [
          "docker compose -f docker-compose.base.yml -f docker-compose.agents.yml --profile agents build notebooklm-agent"
        ]
    } },
    { method: "notify", params: { html: "NotebookLM MCP agent image built. Start it when the agents tier (base networks) is up.", type: "success" } }
  ]
}
