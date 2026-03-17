module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "docker compose -f docker-compose.remote.yml ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'"
        ]
      }
    },
    {
      method: "shell.run",
      params: {
        message: [
          "tailscale status"
        ]
      }
    }
  ]
}
