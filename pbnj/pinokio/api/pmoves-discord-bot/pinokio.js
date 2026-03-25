module.exports = {
  version: "5.0",
  title: "PMOVES Discord Bot",
  description: "CATACLYSM STUDIOS INC community playground bot",
  icon: "icon.png",
  menu: async (kernel, info) => {
    let installing = info.running("install.js")
    let installed = info.exists("app/node_modules")
    let running = info.running("start.js")
    let settingUp = info.running("setup.js")

    if (installing) {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "Installing...",
        href: "install.js"
      }]
    }

    if (settingUp) {
      return [{
        default: true,
        icon: "fa-solid fa-gear",
        text: "Setting up server...",
        href: "setup.js"
      }]
    }

    if (installed) {
      if (running) {
        let local = info.local("start.js")
        return [{
          icon: "fa-solid fa-terminal",
          text: local && local.bot_name ? `Bot: ${local.bot_name}` : "Terminal",
          href: "start.js"
        }, {
          icon: "fa-solid fa-gear",
          text: "Setup Server",
          href: "setup.js"
        }]
      }
      return [{
        default: true,
        icon: "fa-solid fa-power-off",
        text: "Start Bot",
        href: "start.js"
      }, {
        icon: "fa-solid fa-gear",
        text: "Setup Server",
        href: "setup.js"
      }, {
        icon: "fa-solid fa-plug",
        text: "Reinstall",
        href: "install.js"
      }]
    }

    return [{
      default: true,
      icon: "fa-solid fa-plug",
      text: "Install",
      href: "install.js"
    }]
  }
}
