module.exports = {
  daemon: true,
  run: [{
    method: "shell.run",
    params: {
      path: "../../../../pmoves",
      message: ["docker compose up -d nats nats-init"],
      on: [{ event: "/Started|Healthy|running/i", done: true }]
    }
  }]
}
