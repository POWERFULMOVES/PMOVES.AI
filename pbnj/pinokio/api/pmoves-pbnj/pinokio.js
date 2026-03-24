// pbnj/pinokio/api/pmoves-pbnj/pinokio.js
module.exports = {
  version: "5.0",
  title: "PBnJ | PMOVES + Pinokio",
  description: "One-click bridge into your PMOVES lab, KVM4, local dev stacks, and network diagnostics.",
  icon: "icon.png",
  menu: async (kernel, info) => {
    // --------------- State Detection ---------------
    let nettoolsInstalled = info.exists("app/env")

    let running = {
      localUp: info.running("local-up.json"),
      labUp: info.running("lab-up.json"),
      kvm4Up: info.running("kvm4-up.json"),
      install: info.running("install-nettools.js"),
      glancesVenv: info.running("glances-start.js"),
      glancesDocker: info.running("glances-docker.js"),
      netDiag: info.running("net-diag.js"),
      netFix: info.running("net-fix.js"),
      reset: info.running("reset-nettools.js"),
      update: info.running("update.js"),
    }

    let glancesRunning = running.glancesVenv || running.glancesDocker
    let glancesLocal = running.glancesVenv
      ? info.local("glances-start.js")
      : (running.glancesDocker ? info.local("glances-docker.js") : null)

    // --------------- Active Terminal States ---------------
    if (running.install) {
      return [{
        default: true,
        icon: "fa-solid fa-download",
        text: "Installing Network Tools...",
        href: "install-nettools.js",
      }]
    }

    if (running.reset) {
      return [{
        default: true,
        icon: "fa-solid fa-broom",
        text: "Resetting Network Tools...",
        href: "reset-nettools.js",
      }]
    }

    if (running.update) {
      return [{
        default: true,
        icon: "fa-solid fa-arrows-rotate",
        text: "Updating...",
        href: "update.js",
      }]
    }

    // --------------- Build Menu Items ---------------
    let items = []

    // ============ Infrastructure Section ============
    if (running.localUp) {
      items.push({
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
      })
    } else if (running.labUp) {
      items.push({
        icon: "fa-solid fa-terminal",
        text: "AI Lab (Running)",
        href: "lab-up.json",
      }, {
        icon: "fa-solid fa-stop",
        text: "Stop AI Lab",
        href: "lab-down.json",
      })
    } else if (running.kvm4Up) {
      items.push({
        icon: "fa-solid fa-terminal",
        text: "KVM4 Stack (Running)",
        href: "kvm4-up.json",
      }, {
        icon: "fa-solid fa-stop",
        text: "Stop KVM4 Stack",
        href: "kvm4-down.json",
      })
    } else {
      items.push({
        icon: "fa-solid fa-play",
        text: "Local Dev (Docker) — Up",
        href: "local-up.json",
      }, {
        icon: "fa-solid fa-rocket",
        text: "Start AI Lab (K8s)",
        href: "lab-up.json",
      }, {
        icon: "fa-solid fa-server",
        text: "Start KVM4 Stack (K8s)",
        href: "kvm4-up.json",
      })
    }

    // ============ Status Section ============
    items.push({
      icon: "fa-solid fa-circle-info",
      text: "Cluster Status",
      href: "status.json",
    }, {
      icon: "fa-solid fa-satellite-dish",
      text: "VPS Fleet Status",
      href: "vps-status.json",
    })

    // ============ Deploy Section (idle only) ============
    if (!running.localUp && !running.labUp && !running.kvm4Up) {
      items.push({
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
      })
    }

    // ============ Network Tools Section ============
    if (!nettoolsInstalled) {
      // Install prompt
      items.push({
        icon: "fa-solid fa-download",
        text: "Install Network Tools",
        href: "install-nettools.js",
      })
    } else {
      // --- Glances Monitor ---
      if (glancesRunning && glancesLocal && glancesLocal.url) {
        items.push({
          icon: "fa-solid fa-chart-line",
          text: "Open Glances",
          href: glancesLocal.url,
        }, {
          icon: "fa-solid fa-terminal",
          text: "Glances Terminal",
          href: running.glancesVenv ? "glances-start.js" : "glances-docker.js",
        })
      } else if (glancesRunning) {
        items.push({
          icon: "fa-solid fa-spinner",
          text: "Glances (Starting...)",
          href: running.glancesVenv ? "glances-start.js" : "glances-docker.js",
        })
      } else {
        items.push({
          icon: "fa-solid fa-chart-line",
          text: "Start Glances (venv)",
          href: "glances-start.js",
        }, {
          icon: "fa-brands fa-docker",
          text: "Start Glances (Docker)",
          href: "glances-docker.js",
        })
      }

      // --- Network Diagnostics ---
      items.push({
        icon: "fa-solid fa-stethoscope",
        text: "Network Diagnostics",
        href: "net-diag.js",
      })

      // --- Network Fix (diagnostic-first) ---
      items.push({
        icon: "fa-solid fa-wrench",
        text: "Diagnose Issues",
        href: "net-fix.js",
        params: { action: "--diagnose" },
      }, {
        icon: "fa-solid fa-bolt",
        text: "Execute All Fixes (Elevated)",
        href: "net-fix.js",
        params: { action: "--all --execute" },
      }, {
        icon: "fa-solid fa-eraser",
        text: "Flush DNS",
        href: "net-fix.js",
        params: { action: "--flush-dns --execute" },
      }, {
        icon: "fa-solid fa-rotate",
        text: "Reset Network Stack",
        href: "net-fix.js",
        params: { action: "--reset-winsock --execute" },
      }, {
        icon: "fa-solid fa-shield",
        text: "Add Firewall Rules",
        href: "net-fix.js",
        params: { action: "--firewall-add --execute" },
      }, {
        icon: "fa-solid fa-trash-can",
        text: "Clean Docker Networks",
        href: "net-fix.js",
        params: { action: "--docker-clean --execute" },
      })

      // --- Maintenance ---
      items.push({
        icon: "fa-solid fa-arrows-rotate",
        text: "Update",
        href: "update.js",
      }, {
        icon: "fa-regular fa-circle-xmark",
        text: "Reset Network Tools",
        href: "reset-nettools.js",
      })
    }

    // Set default to first item
    if (items.length > 0) {
      items[0].default = true
    }

    return items
  }
}
