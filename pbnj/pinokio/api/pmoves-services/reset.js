module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../../../pmoves",
        message: [
          "make down"
        ]
      }
    },
    {
      method: "notify",
      params: {
        html: "All PMOVES services stopped. Run Install to bootstrap again.",
        type: "warning"
      }
    }
  ]
}
