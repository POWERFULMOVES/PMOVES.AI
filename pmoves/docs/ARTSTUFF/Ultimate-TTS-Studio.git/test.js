module.exports = {
  requires: {
    bundle: "ai",
  },
  run: [
    {
      method: "shell.run",
      params: {
        conda: "tts_env",
        path: "app",
        message: ["python tools/test_engines.py"]
      }
    },
    {
      method: "input",
      params: {
        title: "Engine Test Complete",
        description: "Check the terminal output above for test results."
      }
    }
  ]
}
