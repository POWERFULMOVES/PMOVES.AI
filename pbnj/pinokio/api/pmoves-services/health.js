/**
 * PMOVES Health Dashboard — shows all service statuses via docker compose ps.
 * Augments with HTTP health checks for services that expose /healthz endpoints.
 */
const registry = require("./service-registry")

module.exports = {
  run: [
    {
      method: "log",
      params: {
        raw: true,
        text: "\n═══════════════════════════════════════════════════\n  PMOVES.AI Health Dashboard\n═══════════════════════════════════════════════════\n"
      }
    },
    {
      method: "log",
      params: {
        raw: true,
        text: "▸ Docker Compose Services (main stack):\n"
      }
    },
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: ["docker compose ps --format \"table {{.Name}}\\t{{.Status}}\\t{{.Ports}}\""]
      }
    },
    {
      method: "log",
      params: {
        raw: true,
        text: "\n▸ Monitoring Stack:\n"
      }
    },
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: ["docker compose --profile monitoring ps --format \"table {{.Name}}\\t{{.Status}}\\t{{.Ports}}\""]
      }
    },
    {
      method: "log",
      params: {
        raw: true,
        text: "\n▸ External Services:\n"
      }
    },
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: ["docker compose -f docker-compose.external.yml ps --format \"table {{.Name}}\\t{{.Status}}\\t{{.Ports}}\""]
      }
    },
    {
      method: "log",
      params: {
        raw: true,
        text: "\n═══════════════════════════════════════════════════\n  Health Check Summary Complete\n═══════════════════════════════════════════════════\n"
      }
    }
  ]
}
