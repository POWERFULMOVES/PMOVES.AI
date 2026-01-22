# Codex + Docker MCP — Full Setup

This bundle contains:
- `config.toml` — complete Codex configuration with MCP (Docker), web tool, and four profiles
- `README-Codex-MCP-Full.md` — quick instructions

Windows path for config: `C:\Users\russe\.codex\config.toml`

---

## Profiles

- **web-auto** — Auto-approve, sandboxed writes, network ON (fast day-to-day)
  ```powershell
  codex --profile web-auto
  ```

- **full-send** — Auto-approve, NO sandbox (break-glass mode)
  ```powershell
  codex --profile full-send
  ```

- **mcp-only** — Auto-approve, writes limited to MCP-related paths
  ```powershell
  codex --profile mcp-only
  ```

- **dev** — Auto-approve, local model via Ollama (Codex chats locally)
  ```powershell
  codex --profile dev
  # Ensure model exists:
  # ollama pull qwen2.5:7b-instruct
  ```

---

## MCP (Docker gateway)

Configured under `[mcp_servers.MCP_DOCKER]`:
```toml
[mcp_servers.MCP_DOCKER]
command = "docker"
args    = ["mcp", "gateway", "run"]

[mcp_servers.MCP_DOCKER.env]
LOCALAPPDATA = "C:\Users\russe\AppData\Local"
ProgramData  = "C:\ProgramData"
ProgramFiles = "C:\Program Files"
```

MCP servers are auto-discovered from `mcp_servers` in this file — no `--mcp` flag needed.

---

## Web Access

Enabled via:
```toml
[tools]
web_search = true
```
Use a profile with `sandbox_mode="workspace-write"` and `network_access=true` (e.g., `web-auto`).

---

## Writable Paths

Each profile defines `writable_roots` appropriate to its purpose. Adjust as needed, but prefer **user-space paths** over system folders.

---

## Troubleshooting

- **TOML parse errors around `env = {`** → Inline tables must be single-line. We use subtables instead (e.g., `[mcp_servers.MCP_DOCKER.env]`).
- **No web access** → Ensure you selected a profile that has `network_access=true` in `sandbox_workspace_write`.
- **Local model not found (dev profile)** → Start Ollama and pull the model: `ollama pull qwen2.5:7b-instruct`.
- **Windows path writes denied** → Avoid `C:\Program Files`. Keep writes under your user profile and `ProgramData`.

---

## Suggested Workflow

1. Use `mcp-only` as your default auto-approve session.
2. Switch to `web-auto` when you need broader workspace writes.
3. Use `dev` when you want local LLM responses from Codex itself.
4. Reserve `full-send` for rare cases when you truly need full system access.
