module.exports = {
  version: "5.0",
  title: "PMOVES NotebookLM Agent",
  description: "Build + launch the NotebookLM MCP agent (stdio) on the PMOVES agents tier via the canonical make pipeline. Reached over docker exec; set GOOGLE_REFRESH_TOKEN for live queries.",
  icon: "icon.svg",
  menu: async (kernel, info) => {
    const configured = info.exists("repo-root.txt")
    const running = { install: info.running("install.js"), start: info.running("start.js") }
    if (running.install) return [{ default: true, icon: "fa-solid fa-plug", text: "Funneling secrets...", href: "install.js" }]
    if (running.start)   return [{ default: true, icon: "fa-solid fa-terminal", text: "Starting NotebookLM agent...", href: "start.js" }]
    if (configured) return [
      { default: true, icon: "fa-solid fa-play", text: "Start NotebookLM Agent", href: "start.js" },
      { icon: "fa-solid fa-arrows-rotate", text: "Re-funnel secrets", href: "install.js" }
    ]
    return [{ default: true, icon: "fa-solid fa-download", text: "Set up NotebookLM Agent", href: "install.js" }]
  }
}
