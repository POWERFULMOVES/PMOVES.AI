module.exports = {
  daemon: true,
  run: [{
    method: "shell.run",
    params: {
      path: "../../../../pmoves",
      message: ["docker compose up -d pmoves-yt"],
      on: [{ event: "/Started|Healthy|running/i", done: true }]
    }
  }]
}
