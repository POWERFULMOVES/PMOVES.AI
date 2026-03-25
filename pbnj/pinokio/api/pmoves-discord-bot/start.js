module.exports = {
  daemon: true,
  run: [{
    method: "shell.run",
    params: {
      path: "app",
      message: ["node src/index.js"],
      on: [{
        event: "/Bot ready as (.+)/",
        done: true
      }]
    }
  }, {
    method: "local.set",
    params: {
      bot_name: "{{input.event[1]}}"
    }
  }]
}
