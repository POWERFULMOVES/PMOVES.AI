module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "docker compose --profile agents --profile workers --profile monitoring down"
        ]
      }
    },
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "docker compose -f docker-compose.external.yml down"
        ]
      }
    },
    {
      method: "notify",
      params: {
        html: "All PMOVES services stopped.",
        type: "info"
      }
    }
  ]
}
