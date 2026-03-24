module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "docker compose --profile agents --profile workers --profile orchestration --profile gpu --profile tts --profile cast --profile media --profile botz --profile ui down"
        ]
      }
    },
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "docker compose -f docker-compose.yml -f monitoring/docker-compose.monitoring.yml down"
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
