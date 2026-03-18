// pbnj/pinokio/api/pmoves-pbnj/pinokio.js
module.exports = {
  version: "5.0",
  title: "PBnJ | PMOVES + Pinokio",
  description: "One-click bridge into your PMOVES lab, KVM4, and local dev stacks.",
  icon: "icon.png",
  menu: async (kernel, info) => {
    let running = {
      localUp: info.running("local-up.json"),
      labUp: info.running("lab-up.json"),
      kvm4Up: info.running("kvm4-up.json"),
    }

    // If a script is currently running, show web UI (if available) as default
    if (running.localUp) {
      let localInfo = info.local("local-up.json")
      let items = []
      if (localInfo && localInfo.url) {
        items.push({
          default: true,
          icon: "fa-solid fa-globe",
          text: "Open Web UI",
          href: localInfo.url,
        })
      }
      items.push({
        default: !(localInfo && localInfo.url),
        icon: "fa-solid fa-terminal",
        text: "Local Dev (Running)",
        href: "local-up.json",
      }, {
        icon: "fa-solid fa-stop",
        text: "Stop Local Dev",
        href: "local-down.json",
      }, {
        icon: "fa-solid fa-file-lines",
        text: "Logs",
        href: "local-logs.json",
      }, {
        icon: "fa-solid fa-circle-info",
        text: "Cluster Status",
        href: "status.json",
      })
      return items
    }

    if (running.labUp) {
      let labInfo = info.local("lab-up.json")
      let items = []
      if (labInfo && labInfo.url) {
        items.push({
          default: true,
          icon: "fa-solid fa-globe",
          text: "Open Web UI",
          href: labInfo.url,
        })
      }
      items.push({
        default: !(labInfo && labInfo.url),
        icon: "fa-solid fa-terminal",
        text: "AI Lab (Running)",
        href: "lab-up.json",
      }, {
        icon: "fa-solid fa-stop",
        text: "Stop AI Lab",
        href: "lab-down.json",
      }, {
        icon: "fa-solid fa-circle-info",
        text: "Cluster Status",
        href: "status.json",
      })
      return items
    }

    if (running.kvm4Up) {
      let kvm4Info = info.local("kvm4-up.json")
      let items = []
      if (kvm4Info && kvm4Info.url) {
        items.push({
          default: true,
          icon: "fa-solid fa-globe",
          text: "Open Web UI",
          href: kvm4Info.url,
        })
      }
      items.push({
        default: !(kvm4Info && kvm4Info.url),
        icon: "fa-solid fa-terminal",
        text: "KVM4 Stack (Running)",
        href: "kvm4-up.json",
      }, {
        icon: "fa-solid fa-stop",
        text: "Stop KVM4 Stack",
        href: "kvm4-down.json",
      }, {
        icon: "fa-solid fa-circle-info",
        text: "Cluster Status",
        href: "status.json",
      })
      return items
    }

    // Nothing running — show full menu with Local Dev as default
    return [{
      default: true,
      icon: "fa-solid fa-play",
      text: "Local Dev (Docker) - Up",
      href: "local-up.json",
    }, {
      icon: "fa-solid fa-rocket",
      text: "Start AI Lab (K8s)",
      href: "lab-up.json",
    }, {
      icon: "fa-solid fa-server",
      text: "Start KVM4 Stack (K8s)",
      href: "kvm4-up.json",
    }, {
      icon: "fa-solid fa-circle-info",
      text: "Cluster Status",
      href: "status.json",
    }, {
      icon: "fa-solid fa-file-lines",
      text: "Local Dev Logs",
      href: "local-logs.json",
    }, {
      icon: "fa-solid fa-cloud-arrow-up",
      text: "Deploy KVM4-1 (API)",
      href: "kvm4-1-deploy.json",
    }, {
      icon: "fa-solid fa-database",
      text: "Deploy KVM4-2 (Data)",
      href: "kvm4-2-deploy.json",
    }, {
      icon: "fa-solid fa-shield-halved",
      text: "Deploy KVM2 (Exit)",
      href: "kvm2-deploy.json",
    }, {
      icon: "fa-solid fa-satellite-dish",
      text: "VPS Fleet Status",
      href: "vps-status.json",
    }]
  }
}
