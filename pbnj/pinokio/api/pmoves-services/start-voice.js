module.exports = {
  daemon: true,
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "docker compose --profile orchestration --profile media --profile cast --profile gpu up -d"
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
        url: "http://localhost:8055"
      }
    }
  ]
}
