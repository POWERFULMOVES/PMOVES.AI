module.exports = {
  run: [{
    method: "filepicker.open",
    params: {
      title: "Select PMOVES.AI repository root",
      type: "folder"
    }
  }, {
    method: "local.set",
    params: {
      repo_root: "{{input.paths[0]}}"
    }
  }, {
    method: "fs.write",
    params: {
      path: "repo-root.txt",
      text: "{{local.repo_root}}"
    }
  }, {
    method: "shell.run",
    params: {
      path: "{{path.resolve(local.repo_root, 'pmoves')}}",
      message: [
        "if not exist Makefile ( echo Expected pmoves/Makefile under the selected PMOVES.AI repo root & exit /b 1 )",
        "py -3 tools/env_setup_unified.py",
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
