module.exports = {
  version: "5.0",
  title: "PMOVES NotebookLM Agent",
  description: "Build + launch the NotebookLM MCP agent (stdio) on the PMOVES agents tier. Reached over docker exec — set GOOGLE_REFRESH_TOKEN for live queries.",
  icon: "icon.svg",
  menu: async (kernel, info) => {
    const configured = info.exists("repo-root.txt")
    const running = { install: info.running("install.js"), start: info.running("start.js"), stop: info.running("stop.js") }
    if (running.install) return [{ default: true, icon: "fa-solid fa-plug", text: "Building NotebookLM agent...", href: "install.js" }]
    if (running.stop)    return [{ default: true, icon: "fa-solid fa-broom", text: "Stopping...", href: "stop.js" }]
    if (running.start)   return [
      { default: true, icon: "fa-solid fa-terminal", text: "NotebookLM agent (stdio MCP) — logs", href: "start.js" },
      { icon: "fa-solid fa-stop", text: "Stop", href: "stop.js" }
    ]
    if (configured) return [
      { default: true, icon: "fa-solid fa-play", text: "Start NotebookLM Agent", href: "start.js" },
      { icon: "fa-solid fa-arrows-rotate", text: "Rebuild", href: "install.js" }
    ]
    return [{ default: true, icon: "fa-solid fa-download", text: "Build NotebookLM Agent", href: "install.js" }]
  }
}
