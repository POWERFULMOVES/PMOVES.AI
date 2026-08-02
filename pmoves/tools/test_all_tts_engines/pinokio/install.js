// pmoves/tools/test_all_tts_engines/pinokio/install.js
//
// Gepeto launcher install step for the TTS engine test harness.
// One job: make `gradio_client` importable.
//
// Per gepeto SKILL.md "Package Management" section, prefer `uv` over `pip`.
// Per gepeto SKILL.md "Python Virtual Env" section, use the `venv` attribute
// so the venv is created/used automatically.

module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        venv: "venv",
        path: "../../..",  // pmoves/ (the Python source root)
        message: [
          "uv pip install --upgrade gradio_client",
        ],
      },
    },
  ],
}
