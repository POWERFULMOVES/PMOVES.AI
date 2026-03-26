module.exports = {
  title: "PMOVES Codex",
  icon: "icon.svg",
  description: "OpenAI Codex with PMOVES mesh defaults for Pinokio workspaces.",
  link: "https://github.com/openai/codex",
  run: [{
    when: "{{platform === 'win32'}}",
    id: "run",
    method: "shell.run",
    params: {
      shell: "{{kernel.path('bin/miniconda/Library/bin/bash.exe')}}",
      conda: {
        skip: true
      },
      env: {
        PMOVES_PROVIDER: "openai-codex",
        PMOVES_PINOKIO_PLUGIN: "pmoves-codex",
        PMOVES_AGENT_ZERO_URL: "{{envs.PMOVES_AGENT_ZERO_URL || 'http://localhost:8080'}}",
        PMOVES_AGENT_ZERO_UI_URL: "{{envs.PMOVES_AGENT_ZERO_UI_URL || 'http://localhost:8081'}}",
        PMOVES_ARCHON_URL: "{{envs.PMOVES_ARCHON_URL || 'http://localhost:8091'}}",
        PMOVES_HIRAG_URL: "{{envs.PMOVES_HIRAG_URL || 'http://localhost:8086'}}",
        PMOVES_NOTEBOOK_API_URL: "{{envs.PMOVES_NOTEBOOK_API_URL || 'http://localhost:4110'}}",
        PMOVES_NATS_URL: "{{envs.PMOVES_NATS_URL || 'nats://localhost:4222'}}"
      },
      message: "npx -y @openai/codex@latest {{args.prompt ? JSON.stringify(args.prompt) : ''}}",
      path: "{{args.cwd}}",
      input: true,
      buffer: 1024
    }
  }, {
    when: "{{platform !== 'win32'}}",
    id: "run",
    method: "shell.run",
    params: {
      env: {
        PMOVES_PROVIDER: "openai-codex",
        PMOVES_PINOKIO_PLUGIN: "pmoves-codex",
        PMOVES_AGENT_ZERO_URL: "{{envs.PMOVES_AGENT_ZERO_URL || 'http://localhost:8080'}}",
        PMOVES_AGENT_ZERO_UI_URL: "{{envs.PMOVES_AGENT_ZERO_UI_URL || 'http://localhost:8081'}}",
        PMOVES_ARCHON_URL: "{{envs.PMOVES_ARCHON_URL || 'http://localhost:8091'}}",
        PMOVES_HIRAG_URL: "{{envs.PMOVES_HIRAG_URL || 'http://localhost:8086'}}",
        PMOVES_NOTEBOOK_API_URL: "{{envs.PMOVES_NOTEBOOK_API_URL || 'http://localhost:4110'}}",
        PMOVES_NATS_URL: "{{envs.PMOVES_NATS_URL || 'nats://localhost:4222'}}"
      },
      message: "npx -y @openai/codex@latest {{args.prompt ? JSON.stringify(args.prompt) : ''}}",
      path: "{{args.cwd}}",
      input: true,
      buffer: 1024
    }
  }]
}
