module.exports = {
  daemon: true,
  run: [{
    method: "shell.run",
    params: {
      path: "../../../../pmoves",
      message: ["docker compose --profile agents up -d cipher-api"],
      on: [{ event: "/Started|Healthy|running/i", done: true }]
    }
  }]
}
