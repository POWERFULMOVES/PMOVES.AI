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
        html: "All PMOVES services stopped.",
        type: "info"
      }
    }
  ]
}
