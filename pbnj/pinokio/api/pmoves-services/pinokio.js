module.exports = {
  version: "5.0",
  title: "PMOVES Services",
  description: "One-click control center for all PMOVES.AI Docker Compose services.",
  icon: "icon.png",
  menu: async (kernel, info) => {
    let installed = info.exists("../../pmoves/env.shared")
    let running = {
      core: info.running("start-core.js"),
      voice: info.running("start-voice.js"),
      monitoring: info.running("start-monitoring.js"),
      external: info.running("start-external.js"),
      status: info.running("status.js"),
      install: info.running("install.js"),
      update: info.running("update.js"),
      reset: info.running("reset.js"),
    }

    // Installation in progress
    if (running.install) {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "Installing...",
        href: "install.js",
      }]
    }

    // Not installed yet
    if (!installed) {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "Install (Bootstrap Env)",
        href: "install.js",
      }]
    }

    // Update or reset in progress
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

    // Services running — show active terminals and dashboards
    if (running.core || running.voice || running.monitoring || running.external) {
      let items = []

      if (running.core) {
        let local = info.local("start-core.js")
        if (local && local.url) {
          items.push({
            default: true,
            icon: "fa-solid fa-rocket",
            text: "Open Agent Zero UI",
            href: local.url,
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
        let voiceLocal = info.local("start-voice.js")
        if (voiceLocal && voiceLocal.url) {
          items.push({
            icon: "fa-solid fa-microphone",
            text: "Open Flute Gateway",
            href: voiceLocal.url,
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

      items.push({
        icon: "fa-solid fa-circle-info",
        text: "Health Status",
        href: "status.js",
      })
      items.push({
        icon: "fa-solid fa-stop",
        text: "Stop All",
        href: "stop.js",
      })

      return items
    }

    // Installed but nothing running — show start options
    return [{
      default: true,
      icon: "fa-solid fa-play",
      text: "Start Core (Agents + Workers)",
      href: "start-core.js",
    }, {
      icon: "fa-solid fa-chart-line",
      text: "Start Monitoring",
      href: "start-monitoring.js",
    }, {
      icon: "fa-solid fa-microphone",
      text: "Start Voice (TTS + Flute + Cast)",
      href: "start-voice.js",
    }, {
      icon: "fa-solid fa-puzzle-piece",
      text: "Start External (Wger/Firefly/Jellyfin)",
      href: "start-external.js",
    }, {
      icon: "fa-solid fa-circle-info",
      text: "Health Status",
      href: "status.js",
    }, {
      icon: "fa-solid fa-arrows-rotate",
      text: "Update",
      href: "update.js",
    }, {
      icon: "fa-solid fa-plug",
      text: "Reinstall",
      href: "install.js",
    }, {
      icon: "fa-regular fa-circle-xmark",
      text: "Reset",
      href: "reset.js",
    }]
  }
}
