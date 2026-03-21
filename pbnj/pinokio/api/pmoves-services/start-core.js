module.exports = {
  daemon: true,
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../../../pmoves",
        message: [
          "make up-agents"
        ],
        on: [{
          event: "/Started|running|Attaching|Container.*Started/i",
          done: true
        }]
      }
    },
    {
      method: "local.set",
      params: {
        url: "http://localhost:8081"
      }
    }
  ]
}
