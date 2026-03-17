module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "docker compose --profile agents --profile workers --profile monitoring down -v"
        ]
      }
    },
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "docker compose -f docker-compose.external.yml down -v"
        ]
      }
    },
    {
      method: "notify",
      params: {
        html: "All PMOVES services and volumes reset. Run Install to bootstrap again.",
        type: "warning"
      }
    }
  ]
}
