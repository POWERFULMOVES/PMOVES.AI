module.exports = {
  run: [
    {
      when: "{{!exists('app')}}",
      method: "shell.run",
      params: {
        message: [
          "git clone https://github.com/microsoft/VibeVoice app"
        ]
      }
    },
    {
      method: "script.start",
      params: {
        uri: "torch.js",
        params: {
          path: "app",
          venv: "env"
        }
      }
    },
    {
      method: "shell.run",
      params: {
        venv: "env",
        path: "app",
        message: [
          "uv pip install -e ."
        ]
      }
    },
    {
      method: "hf.download",
      params: {
        path: "app",
        "_": ["microsoft/VibeVoice-Realtime-0.5B"],
        "local-dir": "models/VibeVoice-Realtime-0.5B"
      }
    }
  ]
}

