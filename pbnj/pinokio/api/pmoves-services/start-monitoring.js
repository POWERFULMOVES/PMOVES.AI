module.exports = {
  daemon: true,
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "docker compose --profile monitoring up -d"
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
