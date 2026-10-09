module.exports = {
  daemon: true,
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "docker compose -f docker-compose.external.yml up -d"
        ],
        on: [{
          event: "/Started|running|Attaching/i",
          done: true
        }]
      }
    }
  ]
}
