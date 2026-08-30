// pmoves/tools/test_all_tts_engines/pinokio/pinokio.js
//
// Gepeto launcher UI for the TTS engine test harness.
// Dynamic menu: shows "Install" if venv is missing, "Run all" / "Run one"
// once installed. The "Run one" submenu lists all 14 engines from the
// curated registry, so a reviewer can click any engine and get a
// dedicated test run.
//
// Per gepeto SKILL.md "Dynamic UI rendering" section:
//   - info.exists(relative_path) decides which menu items to show
//   - info.running(relative_path) decides whether to show a stop button
//   - default: the menu item that's auto-selected on first render

const path = require("path")

// The 14 engine ids — sourced from pmoves/tools/test_all_tts_engines.py
// (the harness's ENGINES list). If a new engine is added, update both.
const ENGINES = [
  "kitten_tts",
  "kokoro",
  "f5_tts",
  "indextts",
  "indextts2",
  "fish",
  "fish_s2",
  "chatterbox",
  "chatterbox_turbo",
  "chatterbox_multilingual",
  "voxcpm",
  "higgs",
  "qwen",
  "vibevoice",
]

module.exports = {
  version: "1.0.0",
  title: "TTS Engine Test Harness",
  description:
    "End-to-end test for all 14 TTS engines in Ultimate-TTS-Studio. Uses gradio_client over the real Gradio MCP surface (no mocks). Per-engine review READMEs in pmoves/tools/test_all_tts_engines/engines/. Refactored to use pterm + gepeto (no hand-rolled subprocess wrappers).",

  methods: {
    // Dynamically render the menu based on the current state.
    menu: async (kernel, info) => {
      // info.exists() — relative to the script root (pmoves/tools/test_all_tts_engines/pinokio/)
      const installed = info.exists("venv")

      // info.running() — same path
      const running = info.running("start.js")
      const runningOne = info.running("start-one.js")

      const menu = [
        {
          icon: "fa-info-circle",
          text: "About this launcher",
          method: "about",
        },
      ]

      // Show "Install" only if venv doesn't exist yet
      if (!installed) {
        menu.push({
          icon: "fa-download",
          text: "Install (gradio_client)",
          method: "shell.run",
          params: {
            uri: "install.js",
          },
        })
      } else {
        // Installed — show the test runners
        menu.push({
          icon: "fa-play",
          text: running ? "Stop full run" : "Run all 14 engines",
          method: running ? "script.stop" : "script.start",
          params: running ? { uri: "start.js" } : { uri: "start.js" },
          default: !running && !runningOne,  // auto-select on first render
        })

        // Per-engine submenu
        const engineMenu = ENGINES.map((engineId) => ({
          icon: "fa-microphone",
          text: `Test ${engineId}`,
          method: runningOne ? "script.stop" : "script.start",
          params: {
            uri: "start-one.js",
            params: { engine: engineId },
          },
        }))

        menu.push({
          icon: "fa-list",
          text: "Run a single engine",
          menu: engineMenu,
        })

        // Open the per-engine review READMEs (the "review" half of the lane)
        menu.push({
          icon: "fa-book",
          text: "Per-engine review READMEs",
          method: "shell.run",
          params: {
            message: "explorer ../engines",
          },
        })

        // Open the harness log
        menu.push({
          icon: "fa-file-alt",
          text: "View run log",
          method: "shell.run",
          params: {
            message: "explorer ../logs/api/start.log",
          },
        })
      }

      return menu
    },
  },

  // The "About" handler — explains what this launcher does
  run: [
    {
      method: "log",
      params: {
        text:
          "TTS Engine Test Harness — gradio_client end-to-end over 14 engines. " +
          "Refactored to pterm + gepeto. See ../README.md for the lane overview " +
          "and ../engines/*.md for per-engine review READMEs.",
      },
    },
  ],
}
