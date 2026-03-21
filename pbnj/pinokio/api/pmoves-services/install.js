module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../../../pmoves",
        message: [
          "make env-setup"
        ]
      }
    },
    {
      method: "shell.run",
      params: {
        path: "../../../../pmoves",
        message: [
          "make brand-defaults"
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
