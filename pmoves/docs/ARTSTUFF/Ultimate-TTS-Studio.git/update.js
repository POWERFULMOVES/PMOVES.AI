module.exports = {
  run: [{
    method: "shell.run",
    params: {
      message: "git pull --ff-only"
    }
  }, {
    method: "shell.run",
    params: {
      path: "app",
      message: "git pull --ff-only"
    }
  }, {
    method: "script.start",
    params: {
      uri: "install.js"
    }
  }]
}