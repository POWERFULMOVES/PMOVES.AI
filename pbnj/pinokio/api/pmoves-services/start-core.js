module.exports = {
  daemon: true,
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "docker compose --profile agents --profile workers up -d"
        ],
        on: [{
          event: "/(http:\\/\\/[0-9.:]+)/",
          done: true
        }, {
          event: "/Started|running|Attaching/i",
          done: true
        }]
      }
    },
    {
      method: "local.set",
      params: {
        url: "http://localhost:8081"
      }
    }
  ]
}
