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
          // Docker compose "up -d" never prints an HTTP URL to stdout,
          // so we match on container lifecycle messages instead.
          // The URL below is hardcoded because compose doesn't expose it.
          event: "/Started|running|Attaching/i",
          done: true
        }]
      }
    },
    {
      // Hardcoded: docker compose does not print the service URL to stdout.
      // Agent Zero UI listens on port 8081 by default.
      method: "local.set",
      params: {
        url: "http://localhost:8081"
      }
    }
  ]
}
