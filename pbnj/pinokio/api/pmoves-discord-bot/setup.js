module.exports = {
  run: [{
    method: "shell.run",
    params: {
      path: "app",
      message: ["node src/setup.js"]
    }
  }]
}
