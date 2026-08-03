// pmoves/tools/test_all_tts_engines/pinokio/start.js
//
// Gepeto launcher: run the full TTS engine test harness (all 14 engines).
// Per gepeto SKILL.md "Daemon" section, this is `daemon: true` because the
// underlying Python process is long-lived (each engine takes 10-300s).
//
// After the harness finishes, the post-step uses pterm to:
//   1. Push a desktop notification with the pass/fail summary
//   2. Copy the run summary to the system clipboard
// These are the pterm primitives that replace the hand-rolled wrappers in
// the original test_all_tts_engines.py.

module.exports = {
  daemon: true,
  run: [
    {
      method: "shell.run",
      params: {
        venv: "venv",
        path: "../../..",  // pmoves/ (the Python source root)
        message: [
          "python pmoves/tools/test_all_tts_engines.py --no-play 2>&1 | tee {{cwd}}/logs/api/start.log",
        ],
        on: [
          {
            // Capture the "Working engines" line — the harness prints
            // "  Working engines:" near the end of a successful run.
            event: "/Working engines:/",
            done: true,
          },
          {
            // Or wait for the summary header
            event: "/Summary/",
            done: true,
          },
          {
            // Or wait for the final exit-code-bearing "return 0" or "return 1"
            event: "/return 0|return 1/",
            done: true,
          },
        ],
      },
    },
    {
      // After the harness finishes, push a desktop notification.
      // pterm push is the pterm primitive that replaces the
      // original `_run_pterm(["push", ...])` hand-rolled wrapper.
      method: "shell.run",
      params: {
        // pterm is a Pinokio CLI — resolve it from PATH (no absolute path)
        message: [
          "pterm push \"TTS test suite finished — see logs/api/start.log\" --title \"PMOVES\"",
        ],
      },
    },
    {
      // Copy the run summary to the system clipboard for quick sharing.
      // pterm clipboard write is the pterm primitive that replaces the
      // ad-hoc "save to file then copy" pattern in the original harness.
      method: "shell.run",
      params: {
        message: [
          "pterm clipboard write \"$(tail -30 {{cwd}}/logs/api/start.log)\"",
        ],
      },
    },
  ],
}
