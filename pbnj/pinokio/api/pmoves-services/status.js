module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../../../pmoves",
        message: [
          "make verify-all"
        ]
      }
    }
  ]
}
