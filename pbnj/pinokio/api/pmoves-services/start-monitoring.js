module.exports = {
  daemon: true,
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "docker compose -f docker-compose.yml -f monitoring/docker-compose.monitoring.yml up -d"
        ],
        on: [{
          event: "/Started|running|Attaching/i",
          done: true
        }]
      }
    },
    {
      method: "local.set",
      params: {
        url: "http://localhost:3000"
      }
    }
  ]
}
