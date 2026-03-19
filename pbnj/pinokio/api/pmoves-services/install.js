module.exports = {
  requires: {
    bundle: "ai",
  },
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "python tools/env_setup_unified.py"
        ]
      }
    },
    {
      method: "fs.link",
      params: {
        src: "{{cwd}}",
        dest: "{{path.resolve(cwd, '..', '..', '..', '..', 'pinokio', 'api', 'pmoves-services')}}"
      }
    },
    {
      method: "notify",
      params: {
        html: "PMOVES environment bootstrapped. Ready to start services.",
        type: "success"
      }
    }
  ]
}
