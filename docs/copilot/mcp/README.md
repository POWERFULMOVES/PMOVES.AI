# Copilot MCP Catalogs

Each YAML file defines a trimmed Docker MCP catalog tailored to a Copilot agent mode.

- `mcp_provisioning.yaml`: Supabase + fetch/context utilities for provisioning work.
- `mcp_ui.yaml`: Hostinger, Dart, Playwright stack for website/ui maintenance.
- `mcp_integrations.yaml`: External integrations (Docker Hub, Neo4j, ffmpeg) for ops.

Launch the gateway with one of these catalogs by passing `--catalog <path>` to `docker mcp gateway run`, or duplicate these sections into your Windows `%AppData%\Docker\mcp\catalog.yaml` before starting the gateway.
