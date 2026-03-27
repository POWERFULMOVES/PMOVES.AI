module.exports = {
  run: [{
    method: "fs.read",
    params: {
      path: "repo-root.txt",
      encoding: "utf8"
    }
  }, {
    method: "local.set",
    params: {
      repo_root: "{{input.trim()}}"
    }
  }, {
    method: "shell.run",
    params: {
      path: "{{local.repo_root}}",
      message: [
        "git pull --ff-only origin main",
        "git submodule update --init --recursive"
      ]
    }
  }, {
    method: "shell.run",
    params: {
      path: "{{path.resolve(local.repo_root, 'pmoves')}}",
      message: [
        "py -3 tools/env_setup_unified.py",
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

