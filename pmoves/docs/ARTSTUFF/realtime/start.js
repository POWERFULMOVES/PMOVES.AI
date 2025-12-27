module.exports = {
  daemon: true,
  run: [
    {
      method: "shell.run",
      params: {
        venv: "env",
        env: {
          MODEL_PATH: "models/VibeVoice-Realtime-0.5B",
          MODEL_DEVICE: "{{gpu === 'apple' ? 'mps' : (gpu === 'nvidia' ? 'cuda' : 'cpu')}}"
        },
        path: "app",
        message: [
          "python -m uvicorn demo.web.app:app --host 127.0.0.1 --port {{port}}"
        ],
        on: [{
          event: "/(http:\\/\\/[0-9.:]+)/",
          done: true
        }]
      }
    },
    {
      method: "local.set",
      params: {
        url: "{{input.event[1]}}"
      }
    }
  ]
}
