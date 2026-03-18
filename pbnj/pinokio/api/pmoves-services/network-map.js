/**
 * LAN Service Map — shows all running PMOVES services with their
 * localhost ports and P7 LAN-Wide-Web HTTPS URLs.
 *
 * SECURITY: Clearly marks which services are LAN-safe vs admin-only.
 * Admin services should only be accessed via localhost or SSH tunnel.
 */
const registry = require("./service-registry")

// Pre-compute the service table at load time, with LAN safety annotations
let serviceTable = registry.data.map(s => {
  let port = String(s.uiPort || s.port).padEnd(7)
  let url = ("https://" + (s.uiPort || s.port) + ".localhost").padEnd(32)
  let access = s.lanSafe ? "LAN OK" : "LOCAL"
  let marker = s.lanSafe ? "  " : "! "
  return marker + s.label.padEnd(22) + " " + port + " " + url + " " + access
}).join("\n")

module.exports = {
  run: [
    {
      method: "log",
      params: {
        raw: true,
        text: "\n\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\n  PMOVES.AI LAN Service Map (P7 LWW)\n\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\n"
      }
    },
    {
      method: "log",
      params: {
        raw: true,
        text: "\u25b8 Running Docker Containers:\n"
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
        text: "\n\u2500\u2500 Registered Services & LWW URLs \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n  Service               Port    HTTPS URL                        Access\n  \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n" + serviceTable + "\n  \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n  SECURITY NOTICE:\n  ! = LOCAL only (admin/data service, do NOT expose on LAN)\n      Access via localhost or SSH tunnel only.\n      Exposing these services risks credential theft and data exfil.\n\n  LAN OK = Safe for P7 LAN-Wide-Web discovery.\n      Custom domains: Run 'Setup Custom Domains' from the menu.\n"
      }
    }
  ]
}
