module.exports = {
  version: "5.0",
  title: "PMOVES Model Selector",
  description: "UI over the model-registry (:8110) + gpu-orchestrator (:8200) APIs, plus a gfx1201 llama-server GGUF lane on :8090. No hardcoded models.",
  icon: "icon.svg",
  menu: async (kernel, info) => {
    // "Installed" == the gfx1201 llama.cpp fork has been cloned + built.
    let built = info.exists("llama.cpp-rdna4-gfx1201/build/bin/llama-server")

    let running = {
      install: info.running("install.js"),
      start: info.running("start.js"),
      select: info.running("select-model.js"),
      reset: info.running("reset.js"),
      update: info.running("update.js")
    }

    if (running.install) {
      return [{
        default: true,
        icon: "fa-solid fa-hammer",
        text: "Building llama.cpp (gfx1201)...",
        href: "install.js"
      }]
    }
    if (running.reset) {
      return [{
        default: true,
        icon: "fa-solid fa-broom",
        text: "Resetting...",
        href: "reset.js"
      }]
    }
    if (running.update) {
      return [{
        default: true,
        icon: "fa-solid fa-arrows-rotate",
        text: "Updating...",
        href: "update.js"
      }]
    }

    // The select/load + unload UI is always available (it only needs the
    // registry :8110 / gpu-orchestrator :8200 services, not the local build).
    let selectItems = [{
      icon: "fa-solid fa-layer-group",
      text: "Select & Load Model",
      href: "select-model.js"
    }, {
      icon: "fa-solid fa-eject",
      text: "Unload Model",
      href: "select-model.js",
      params: { action: "unload" }
    }]

    if (!built) {
      return [{
        default: true,
        icon: "fa-solid fa-hammer",
        text: "Install (build llama.cpp gfx1201)",
        href: "install.js"
      }].concat(selectItems, [{
        icon: "fa-solid fa-book",
        text: "gpu-orchestrator loaded models",
        href: "http://127.0.0.1:8200/api/gpu/models/loaded"
      }, {
        icon: "fa-solid fa-list",
        text: "registry catalog (:8110)",
        href: "http://127.0.0.1:8110/api/models"
      }])
    }

    let local = info.local("start.js")
    let uiUrl = local && local.url ? local.url : "http://127.0.0.1:8090"

    let items = [{
      default: true,
      icon: running.start ? "fa-solid fa-terminal" : "fa-solid fa-play",
      text: running.start ? "llama-server Terminal (:8090)" : "Start llama-server (GGUF, :8090)",
      href: "start.js"
    }, {
      icon: "fa-solid fa-globe",
      text: "Open llama-server UI",
      href: uiUrl
    }, {
      icon: "fa-solid fa-diagram-project",
      text: "llama-server /v1/models",
      href: "http://127.0.0.1:8090/v1/models"
    }]
    .concat(selectItems)
    .concat([{
      icon: "fa-solid fa-book",
      text: "gpu-orchestrator loaded models",
      href: "http://127.0.0.1:8200/api/gpu/models/loaded"
    }, {
      icon: "fa-solid fa-list",
      text: "registry catalog (:8110)",
      href: "http://127.0.0.1:8110/api/models"
    }, {
      icon: "fa-solid fa-arrows-rotate",
      text: "Update",
      href: "update.js"
    }, {
      icon: "fa-solid fa-broom",
      text: "Reset (remove build)",
      href: "reset.js"
    }])

    return items
  }
}
