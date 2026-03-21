module.exports = {
  daemon: true,
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../../../pmoves",
        message: [
          "make up"
        ],
        on: [{
          event: "/Started|running|Attaching|Container.*Started/i",
          done: true
        }]
      }
    }
  ]
}
