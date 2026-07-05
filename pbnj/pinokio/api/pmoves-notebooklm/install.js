// Prepare the PMOVES env for the NotebookLM MCP agent. Picks the repo root once,
// then runs the CANONICAL secrets pipeline (make secrets-funnel) so COMPOSE_ENV_FILES
// / tier env files exist before launch. Does NOT call docker compose directly.
module.exports = {
  run: [
    { method: "filepicker.open", params: { title: "Select PMOVES.AI repository root", type: "folder" } },
    { method: "local.set", params: { repo_root: "{{input.paths[0]}}" } },
    { method: "fs.write", params: { path: "repo-root.txt", text: "{{local.repo_root}}" } },
    { method: "shell.run", params: {
        path: "{{path.resolve(local.repo_root, 'pmoves')}}",
        message: [ "make secrets-funnel" ]
    } },
    { method: "notify", params: { html: "PMOVES secrets funneled. Start the NotebookLM MCP agent when ready.", type: "success" } }
  ]
}
