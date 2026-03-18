module.exports = {
  daemon: true,
  run: [{
    method: "shell.run",
    params: {
      path: "../../../../pmoves",
      message: ["docker compose up -d archon"],
      on: [{ event: "/Started|Healthy|running/i", done: true }]
    }
  }, {
    method: "local.set",
    params: { url: "http://localhost:3737" }
  }]
}
