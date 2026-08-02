// pmoves/tools/test_all_tts_engines/pinokio/start-one.js
//
// Gepeto launcher: run the TTS harness against ONE engine.
// The engine id is passed via the Pinokio UI as `args.engine`.
//
// Per gepeto SKILL.md "Quick scripts" section, this is a script launcher
// without a web UI — the user picks the engine in Pinokio's menu, then
// clicks "Run" and the test for that engine executes.
//
// Per gepeto SKILL.md "AI Libraries" section, the parent install.js
// already declares the `ai` bundle so the harness has CUDA + HuggingFace CLI.

module.exports = {
  daemon: true,
  run: [
    {
      method: "shell.run",
      params: {
        venv: "venv",
        path: "../../..",  // pmoves/ (the Python source root)
        message: [
          "python pmoves/tools/test_all_tts_engines.py --engine \"{{args.engine}}\" --no-play 2>&1 | tee {{cwd}}/logs/api/start-one-{{args.engine}}.log",
        ],
        on: [
          // Stop polling once we hit the summary block
          { event: "/Summary/", done: true },
          { event: "/return 0|return 1/", done: true },
        ],
      },
    },
    {
      // Notify — same pterm primitive as start.js, with the engine id
      method: "shell.run",
      params: {
        message: [
          "pterm push \"TTS test ({{args.engine}}) finished — see logs/api/start-one-{{args.engine}}.log\" --title \"PMOVES\"",
        ],
      },
    },
  ],
}
