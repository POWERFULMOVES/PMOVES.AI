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
        html: "Core, worker, monitoring, and external services reset. Run Install to bootstrap again.",
        type: "warning"
      }
    }
  ]
}
