module.exports = {
  run: [{
    method: "shell.run",
    params: {
      path: "../../../..",
      message: [
        "git pull --ff-only origin main",
        "git submodule update --init --recursive"
      ]
    }
  }, {
    method: "shell.run",
    params: {
      path: "../../../../pmoves",
      message: [
        "python tools/env_setup_unified.py",
        "make a0-mcp-seed"
      ]
    }
  }, {
    method: "notify",
    params: {
      html: "PMOVES Agent Zero launcher updated and MCP runtime reseeded.",
      type: "success"
    }
  }]
}
