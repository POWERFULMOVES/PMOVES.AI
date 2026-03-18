module.exports = {
  daemon: true,
  run: [{
    method: "shell.run",
    params: {
      path: "../../../../pmoves",
      message: ["docker compose up -d deepresearch"],
      on: [{ event: "/Started|Healthy|running/i", done: true }]
    }
  }]
}
