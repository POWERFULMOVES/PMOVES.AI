// PMOVES Demo Room launcher
// Starts Agent Zero (local Python), surfaces the WebUI, publishes p7.nats.launch.
// Graceful NATS skip if the bus is not reachable.
module.exports = {
  daemon: true,
  run: [
    {
      method: "log",
      params: { text: "PMOVES Demo Room — starting Agent Zero + HERMES V4" }
    },
    {
      // Save the next available port before launching so we can construct localhost URL cleanly
      method: "local.set",
      params: { port: "{{port}}" }
    },
    {
      method: "shell.run",
      params: {
        // Use PMOVES_ROOT env var — same convention as all other PBnJ launchers
        path: "{{envs.PMOVES_ROOT}}/PMOVES-Agent-Zero",
        venv: ".venv",
        message: ["python run_ui.py --port {{local.port}}"],
        on: [{
          // Matches both "Running on http://..." and "Uvicorn running on http://..."
          event: "/(http:\\/\\/[^\\s]+)/",
          done: true
        }]
      }
    },
    {
      method: "local.set",
      params: {
        url: "http://localhost:{{local.port}}"
      }
    },
    {
      method: "web.open",
      params: { url: "{{local.url}}" }
    },
    {
      // Publish p7.nats.launch — skip gracefully if NATS CLI not in PATH or bus is down
      method: "shell.run",
      params: {
        message: [
          "nats pub p7.nats.launch \"{\\\"room\\\":\\\"demo.room.rehearsal\\\",\\\"stage\\\":\\\"rehearsal\\\",\\\"suits\\\":[\\\"agent-zero-local\\\",\\\"4090-claws\\\",\\\"hermes-v4\\\"]}\" 2>nul || echo NATS skip"
        ]
      }
    },
    {
      method: "notify",
      params: {
        title: "PMOVES Demo Room",
        message: "Agent Zero ready at {{local.url}}"
      }
    }
  ]
}
