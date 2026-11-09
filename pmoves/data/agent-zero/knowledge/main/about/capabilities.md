# Agent Zero Capabilities

Agent Zero can:
- run terminal and code execution tools inside the Docker/server runtime
- use A0 CLI connector tools for host/local machine execution when connected and enabled
- read, write, and patch files with text editor tools
- browse the web with the browser/search tools
- create and query document artifacts
- save, load, and forget memories
- schedule tasks
- call subordinate agents
- use MCP and A2A integrations when configured

Important boundary:
- Docker/server tools operate inside the Agent Zero container, usually `/a0/usr/workdir`.
- A0 CLI remote tools operate on the connected host machine, usually the CLI working directory.
- Do not confuse host-local paths with container paths.

Capabilities depend on enabled plugins, settings, model quality, permissions, and active project context.
