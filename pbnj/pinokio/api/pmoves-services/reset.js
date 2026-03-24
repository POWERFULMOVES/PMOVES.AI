module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "docker compose --profile agents --profile workers --profile orchestration --profile gpu --profile tts --profile cast --profile media --profile botz --profile ui down -v"
        ]
      }
    },
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "docker compose -f docker-compose.yml -f monitoring/docker-compose.monitoring.yml down -v"
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
