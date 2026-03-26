module.exports = {
  version: "5.0",
  title: "PMOVES Agent Zero",
  description: "Launch Agent Zero from the PMOVES mesh and seed its MCP runtime.",
  icon: "icon.svg",
  menu: async (kernel, info) => {
    let configured = info.exists("repo-root.txt")
    let running = {
      install: info.running("install.js"),
      start: info.running("start.js"),
      status: info.running("status.js"),
      reset: info.running("reset.js"),
      update: info.running("update.js")
    }

    if (running.install) {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "Bootstrapping Agent Zero...",
        href: "install.js"
      }]
    }

    if (running.reset) {
      return [{
        default: true,
        icon: "fa-solid fa-broom",
        text: "Resetting Agent Zero...",
        href: "reset.js"
      }]
    }

    if (running.update) {
      return [{
        default: true,
        icon: "fa-solid fa-arrows-rotate",
        text: "Updating Agent Zero...",
        href: "update.js"
      }]
    }

    if (!configured) {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "Install (Select PMOVES Repo)",
        href: "install.js"
      }]
    }

    let local = info.local("start.js")
    let uiUrl = local && local.url ? local.url : "http://localhost:8081"

    let items = [{
      default: true,
      icon: running.start ? "fa-solid fa-terminal" : "fa-solid fa-play",
      text: running.start ? "Agent Zero Terminal" : "Start Agent Tier",
      href: "start.js"
    }, {
      icon: "fa-solid fa-globe",
      text: "Open Agent Zero UI",
      href: uiUrl
    }, {
      icon: "fa-solid fa-book",
      text: "Open API Docs",
      href: "http://localhost:8080/docs"
    }, {
      icon: "fa-solid fa-heart-pulse",
      text: "Health Check",
      href: "http://localhost:8080/healthz"
    }, {
      icon: "fa-solid fa-diagram-project",
      text: "MCP Commands",
      href: "http://localhost:8080/mcp/commands"
    }, {
      icon: "fa-solid fa-folder-tree",
      text: "Re-select PMOVES Repo",
      href: "install.js"
    }, {
      icon: "fa-solid fa-circle-info",
      text: "Status",
      href: "status.js"
    }, {
      icon: "fa-solid fa-arrows-rotate",
      text: "Update + Reseed MCP",
      href: "update.js"
    }, {
      icon: "fa-solid fa-broom",
      text: "Reset Runtime",
      href: "reset.js"
    }]

    return items
  }
}
