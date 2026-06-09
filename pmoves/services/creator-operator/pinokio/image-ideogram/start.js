// Starts ComfyUI and captures the local URL so the chrome-devtools operator
// knows where to navigate. See .claude/PINOKIO_LAUNCHER_GUIDE.md (URL capture).
//
// Per the guide's Critical Pattern Lock: the `event` regex wraps the URL in a
// capture group and `local.set` reads the captured match via `input.event[1]`
// (index 1 = the parenthesized group), NOT input.event[0].
module.exports = {
  daemon: true,
  run: [
    {
      method: "shell.run",
      params: {
        path: "ComfyUI",
        venv: "venv",
        message: "python main.py --listen 127.0.0.1 --port 8188",
        on: [{ event: "/(http:\\/\\/[0-9.:]+)/", done: true }],
      },
    },
    { method: "local.set", params: { url: "{{input.event[1]}}" } },
  ],
};
