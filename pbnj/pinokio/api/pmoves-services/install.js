module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "py -3 tools/env_setup_unified.py"
        ]
      }
    },
    {
      method: "notify",
      params: {
        html: "PMOVES environment bootstrapped. Ready to start services.",
        type: "success"
      }
    }
  ]
}
