module.exports = {
  version: "5.0",
  title: "PMOVES Remote",
  description: "Headscale VPN + RustDesk remote desktop for multi-node PMOVES deployment.",
  menu: async (kernel, info) => {
    let installed = info.exists("../../pmoves/env.tier-vpn")
    let running = {
      start: info.running("start.js"),
      install: info.running("install.js"),
      status: info.running("status.js"),
    }

    if (running.install) {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "Installing...",
        href: "install.js",
      }]
    }

    if (!installed) {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "Install (Setup VPN Env)",
        href: "install.js",
      }]
    }

    if (running.start) {
      let local = info.local("start.js")
      let items = []
      if (local && local.url) {
        items.push({
          default: true,
          icon: "fa-solid fa-globe",
          text: "Open Headscale Admin",
          href: local.url,
        })
      }
      items.push({
        icon: "fa-solid fa-terminal",
        text: "Remote Stack (Running)",
        href: "start.js",
      })
      items.push({
        icon: "fa-solid fa-satellite-dish",
        text: "Mesh Status",
        href: "status.js",
      })
      return items
    }

    return [{
      default: true,
      icon: "fa-solid fa-play",
      text: "Start (Headscale + RustDesk)",
      href: "start.js",
    }, {
      icon: "fa-solid fa-satellite-dish",
      text: "Mesh Status",
      href: "status.js",
    }, {
      icon: "fa-solid fa-plug",
      text: "Reinstall",
      href: "install.js",
    }]
  }
}
