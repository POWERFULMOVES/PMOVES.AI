# Claude Desktop -- scoped MCP template

Claude Desktop runs **no damage-control hooks** and does **not** expand `${VAR}`.
Any folder it can open is fully readable, secret files included. So the scope lives
in the folder list itself: it names only directories that hold no zero-access files
(`zeroAccessPaths` in `.claude/hooks/damage-control/patterns.yaml`).
`pmoves/tests/test_harness_scope_team.py` enforces that on every checkout.

| File | Platform |
|---|---|
| `claude_desktop_config.windows.json` | Windows (`cmd /c npx`, backslash paths) |
| `claude_desktop_config.macos.json` | macOS (`npx`, forward-slash paths) |

Claude Desktop has no Linux build. On Linux nodes, use Claude Code (`claude-pmoves.sh`).

## What it opens, and why

| Folder | Why |
|---|---|
| `pmoves/config` | agent registry, rooms, signing identity cards |
| `pmoves/docs/handoffs` | briefs, including the identity/team scope model |
| `pmoves/docs/AGENTS` | claim register and sitrep |
| `.claude/agents` | subagent definitions |

It does **not** open the repo root, `pmoves/` as a whole, or any drive root. All
of those contain env files or keys. To open more, add a folder and let the test
check it; never widen a root to one the test rejects.

## Not included

- **Docker MCP gateway.** If the node's Docker engine runs Windows containers
  (`docker info --format '{{.OSType}}'` = `windows`), Docker access is host-admin
  (`ContainerAdministrator` is a local administrator on the host). Add it per node,
  deliberately, and record that it is host scope.
- **Servers that need secrets.** Desktop cannot resolve `${VAR}`, so a token would
  have to be written into the file. Leave those servers out.

## Applying it on a node (operator)

1. Measure the platform first: `uname -s` or `$PSVersionTable`, and the repo path.
2. Back up the live config:
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
3. Copy the `pmoves-filesystem` entry into its `mcpServers` and replace
   `<PMOVES_REPO>` with the node's checkout path. Keep the node's other entries.
4. Restart Claude Desktop.

Agents do not apply this. The live Desktop config is a node setting and belongs to
the operator. `harness-scope-auditor` reports drift between the two.
