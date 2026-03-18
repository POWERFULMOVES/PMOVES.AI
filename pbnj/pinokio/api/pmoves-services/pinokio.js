const registry = require("./service-registry")

// ── Security: Validate URLs from local variables (never trust script output) ──
const SAFE_URL_RE = /^https?:\/\/(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?(?:\/.*)?$/
function safeUrl(url) {
  return typeof url === "string" && SAFE_URL_RE.test(url) ? url : null
}

// ── Security: Validate service/group names (alphanumeric + hyphen only) ──
const SAFE_NAME_RE = /^[a-z0-9\-]+$/
function safeName(name) {
  return typeof name === "string" && SAFE_NAME_RE.test(name)
}

module.exports = {
  version: "6.0.0",
  title: "PMOVES Services",
  description: "One-click control center for all PMOVES.AI Docker Compose services — agents, workers, monitoring, and external integrations.",
  menu: async (kernel, info) => {
    let installed = info.exists("../../pmoves/env.shared")

    let running = {
      core:       info.running("start-core.js"),
      voice:      info.running("start-voice.js"),
      monitoring: info.running("start-monitoring.js"),
      external:   info.running("start-external.js"),
      install:    info.running("install.js"),
      update:     info.running("update.js"),
      reset:      info.running("reset.js"),
    }

    // ── Installation in progress ──
    if (running.install) {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "Installing...",
        href: "install.js",
      }]
    }

    // ── Not installed yet ──
    if (!installed) {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "Install (Bootstrap Env)",
        href: "install.js",
      }]
    }

    // ── Update or reset in progress ──
    if (running.update) {
      return [{
        default: true,
        icon: "fa-solid fa-arrows-rotate",
        text: "Updating...",
        href: "update.js",
      }]
    }
    if (running.reset) {
      return [{
        default: true,
        icon: "fa-solid fa-rotate-left",
        text: "Resetting...",
        href: "reset.js",
      }]
    }

    // ── Services running — show active terminals, dashboards, and individual controls ──
    if (running.core || running.voice || running.monitoring || running.external) {
      let items = []

      // Active service terminals and UIs
      if (running.core) {
        let coreUrl = safeUrl((info.local("start-core.js") || {}).url)
        if (coreUrl) {
          items.push({
            default: true,
            icon: "fa-solid fa-rocket",
            text: "Open Agent Zero UI",
            href: coreUrl,
          })
        }
        items.push({
          icon: "fa-solid fa-terminal",
          text: "Core Services (Running)",
          href: "start-core.js",
        })
      }

      if (running.monitoring) {
        items.push({
          default: !running.core,
          icon: "fa-solid fa-chart-line",
          text: "Open Grafana",
          href: "http://localhost:3000",
        })
        items.push({
          icon: "fa-solid fa-terminal",
          text: "Monitoring (Running)",
          href: "start-monitoring.js",
        })
      }

      if (running.voice) {
        let voiceUrl = safeUrl((info.local("start-voice.js") || {}).url)
        if (voiceUrl) {
          items.push({
            icon: "fa-solid fa-microphone",
            text: "Open Flute Gateway",
            href: voiceUrl,
          })
        }
        items.push({
          icon: "fa-solid fa-terminal",
          text: "Voice Pipeline (Running)",
          href: "start-voice.js",
        })
      }

      if (running.external) {
        items.push({
          icon: "fa-solid fa-terminal",
          text: "External (Running)",
          href: "start-external.js",
        })
      }

      // Individual service submenus (available while running)
      items.push(...buildServiceSubmenus(info))

      // Tools
      items.push({
        icon: "fa-solid fa-heart-pulse",
        text: "Health Dashboard",
        href: "health.js",
      })
      items.push({
        icon: "fa-solid fa-network-wired",
        text: "LAN Service Map",
        href: "network-map.js",
      })
      items.push({
        icon: "fa-solid fa-stop",
        text: "Stop All",
        href: "stop.js",
      })

      return items
    }

    // ── Installed but nothing running — full menu ──
    let items = [
      // Start All shortcuts
      {
        default: true,
        icon: "fa-solid fa-play",
        text: "Start Core (Agents + Workers)",
        href: "start-core.js",
      },
      {
        icon: "fa-solid fa-chart-line",
        text: "Start Monitoring",
        href: "start-monitoring.js",
      },
      {
        icon: "fa-solid fa-microphone",
        text: "Start Voice (TTS + Flute + Cast)",
        href: "start-voice.js",
      },
      {
        icon: "fa-solid fa-puzzle-piece",
        text: "Start External (Wger/Firefly/Jellyfin)",
        href: "start-external.js",
      },

      // Individual service submenus
      ...buildServiceSubmenus(info),

      // Tools
      {
        icon: "fa-solid fa-heart-pulse",
        text: "Health Dashboard",
        href: "health.js",
      },
      {
        icon: "fa-solid fa-network-wired",
        text: "LAN Service Map",
        href: "network-map.js",
      },
      {
        icon: "fa-solid fa-book",
        text: "Ingest Pinokio Docs",
        href: "ingest-pinokio-docs.js",
      },
      {
        icon: "fa-solid fa-globe",
        text: "Setup Custom Domains",
        href: "setup-domains.js",
      },

      // Maintenance
      {
        icon: "fa-solid fa-arrows-rotate",
        text: "Update",
        href: "update.js",
      },
      {
        icon: "fa-solid fa-plug",
        text: "Reinstall",
        href: "install.js",
      },
      {
        icon: "fa-regular fa-circle-xmark",
        text: "Reset",
        href: "reset.js",
      },
    ]

    return items
  }
}

/**
 * Build nested submenu items for each service group.
 * Each group expands into individual service start scripts.
 *
 * Security: validates all names from registry against SAFE_NAME_RE
 * to prevent path traversal via poisoned service-registry.js entries.
 * URLs from local variables are validated via safeUrl() to block
 * javascript: / data: URI injection.
 */
function buildServiceSubmenus(info) {
  let groups = registry.groups
  let submenus = []

  for (let [groupKey, groupMeta] of Object.entries(groups)) {
    if (!safeName(groupKey)) continue  // skip poisoned group keys

    let services = registry.byGroup(groupKey)
    let menu = services.map(svc => {
      let scriptName = svc.script || svc.name
      if (!safeName(scriptName)) return null  // skip poisoned service names

      let scriptPath = `services/${groupKey}/start-${scriptName}.js`
      let item = {
        icon: groupMeta.icon,
        text: svc.label,
        href: scriptPath,
      }

      // If service has a UI and is running, link to the UI
      if (svc.ui && info.running(scriptPath)) {
        let localUrl = safeUrl((info.local(scriptPath) || {}).url)
        if (localUrl) {
          item.href = localUrl
        }
      }

      return item
    }).filter(Boolean)

    submenus.push({
      icon: groupMeta.icon,
      text: groupMeta.label,
      menu: menu,
    })
  }

  return submenus
}
