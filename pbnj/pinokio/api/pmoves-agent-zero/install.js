module.exports = {
  run: [{
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
      html: "PMOVES environment bootstrapped for Agent Zero. Start the agent tier when ready.",
      type: "success"
    }
  }]
}


