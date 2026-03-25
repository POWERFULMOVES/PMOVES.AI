module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "../..",
        message: [
          "git pull --ff-only origin main",
          "git submodule update --init --recursive"
        ]
      }
    },
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
        html: "PMOVES updated to latest.",
        type: "success"
      }
    }
  ]
}
