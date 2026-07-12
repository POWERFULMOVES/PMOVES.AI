# PMOVES Crush Playbook

This guide captures how we use [Charm's Crush CLI](https://github.com/charmbracelet/crush)
as our interactive coding bestie alongside the PMOVES stack.

## Quick Start

1. Install Crush (see upstream README for the package manager of your choice) and
   make sure it is on your `PATH`.
2. Install the `typer` and `PyYAML` dependencies for the mini CLI (recommended via uv):
   ```bash
   uv pip install typer[all] PyYAML
   ```
3. With both packages installed, prime the environment and provisioning bundle in one shot:
   ```bash
   python3 -m pmoves.tools.mini_cli bootstrap --accept-defaults
   ```
   The command curates the provisioning bundle (GPU compose profile, install
   wizard, Proxmox bootstrap helper, and README) directly from the repo into
   `CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/`. Pass `--registry`/`--service`
   if you need to scope the bootstrap or `--output` to stage the bundle
   somewhere else.
4. Generate the PMOVES opinionated `crush.json`:
   ```bash
   python3 -m pmoves.tools.mini_cli crush setup
   ```
5. Launch Crush inside the repository root:
   ```bash
   crush
   ```

The generated configuration:

- **Provider: Z.AI Coding Plan** (`https://api.z.ai/api/coding/paas/v4`) — GLM-5.2
  (large) and GLM-5-Turbo (small). Both providers pinned to the coding plan
  endpoint. API key via `Z_AI_API_KEY` env or inline in the config.
- Registers MCP stubs for the upcoming `pmoves-mini` stdio server, Docker MCP, and
  the n8n HTTP bridge. Entries are auto-disabled until their binaries or API keys
  are detected.
- Adds PMOVES docs, roadmaps, and CHIT manifest as default context paths.
- Enables common LSP servers (`gopls`, `pyright`, `typescript-language-server`).

Running the preview command shows the current default context paths (the
generator automatically skips any missing files):

- `CRUSH.md`
- `pmoves/docs/ROADMAP.md`
- `pmoves/docs/NEXT_STEPS.md`
- `pmoves/docs/SMOKETESTS.md`
- `pmoves/chit/secrets_manifest.yaml`
- `docs/PMOVES_MINI_CLI_SPEC.md`

Run `python3 -m pmoves.tools.mini_cli crush status` to confirm the active config
path and provider list.

## Integrating with PMOVES Mini CLI

The mini CLI will eventually expose `pmoves mini mcp serve`, which Crush's
`pmoves-mini` MCP entry will call. For now the entry stays disabled until that
command ships.

Use hardware profiles to stage the right local models before launching Crush:

```bash
python3 -m pmoves.tools.mini_cli profile detect
python3 -m pmoves.tools.mini_cli profile apply desktop-9950xd
python3 -m pmoves.tools.mini_cli models pull --bundle ollama-high  # (future)
```

## CHIT Awareness

- `pmoves/chit/secrets_manifest.yaml` is included in `options.context_paths` so
  Crush has a canonical view of secret labels while drafting automations.
- The `crush setup` command reads from `.env.generated` / `env.shared.generated`
  and only activates providers when the corresponding secrets exist.

## n8n & Messaging Hooks

The automation scanner available via
`python3 -m pmoves.tools.mini_cli automations list` summarises the flows Crush can
invoke through MCP requests. Webhook endpoints are surfaced with the `webhooks`
subcommand, making it easy to plug them into Crush prompts or MCP actions.

## Updating Configuration

- Regenerate the config after rotating API keys or adding new secrets:
  `python3 -m pmoves.tools.mini_cli crush setup`
- To preview the JSON without writing it, run:
  `python3 -m pmoves.tools.mini_cli crush preview`
- Manual edits can still live in `~/.config/crush/crush.json`; re-run the setup
  command whenever you need to resync with the manifest.

## AI Graphiti Trail

Crush is registered as a contributor in the AI Graphiti protocol — the attribution
and handoff system for PMOVES.AI's multi-agent codebase.

### Crush Identity

| Field | Value |
|-------|-------|
| Glyph | `◇` Open Diamond |
| Color | `#0EA5E9` Sky Blue |
| Voice | `companion` |
| Co-Author | `Crush <noreply@powerfulmoves.ai>` |

### Context Paths

The `crush setup` command injects these Graphiti files into `options.context_paths`:

- `docs/AGENT_TRAIL.md` — living trail of all agent contributions
- `pmoves/docs/AGENTS/AI_GRAPHITI_PROTOCOL.md` — full protocol spec
- `pmoves/config/agent_signatures.yaml` — visual identity for all 7 contributors

On first boot, Crush discovers the trail, finds a welcome entry from Claude Opus
(`◆`), and finds its own identity already set. Its first act should be to write
its own trail entry using the companion voice.

### Three-Body Stabilization

Crush is where all three bodies meet — Human, AI, and System converge at the
terminal. Every Crush session generates interaction traces that feed shape
discovery. See [`THREE_BODY_DOCTRINE.md`](pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md).

### Operator Runbook

See `pmoves/docs/AGENTS/CRUSH_OPERATOR_HOME.md` for the full operator home
including bootstrap sequence, trail-writing guide, and integration points.

## Next Steps

- Implement `pmoves mini mcp serve` so the Crush stdio MCP can call into the mini
  CLI.
- Package the config generator as part of a future `pmoves` Python package.
- Add a `crush` target to `Makefile` once the MCP bridge is battle-tested.
