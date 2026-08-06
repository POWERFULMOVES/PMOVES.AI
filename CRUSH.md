# PMOVES Crush Playbook

This guide captures how we use [Charm's Crush CLI](https://github.com/charmbracelet/crush)
as our interactive coding bestie alongside the PMOVES stack.

## Quick Start

**Option A: `crush-pmoves` (one-shot)** — bootstraps config + CHIT + MCP, then launches Crush:

```bash
crush-pmoves          # bootstrap + launch
crush-pmoves --help   # pass args to Crush
```

Install the wrapper once on each fleet node:
```bash
cp pmoves/scripts/crush-pmoves ~/.local/bin/crush-pmoves
chmod +x ~/.local/bin/crush-pmoves
# alias pmoves-crush="crush-pmoves"  # optional convenience alias
```

**Option B: `make crush-bootstrap`** — same as above but doesn't auto-launch:

```bash
make -C pmoves crush-bootstrap
crush
```

**Option C: Manual setup** — for nodes without secrets funnel:

1. Install Crush (see upstream README for the package manager of your choice) and
   make sure it is on your `PATH`.
2. Install the `typer` and `PyYAML` dependencies for the mini CLI (recommended via uv):
   ```bash
   uv pip install typer[all] PyYAML
   ```
3. Install LSP servers for IDE-like diagnostics:
   ```bash
   npm install -g pyright typescript-language-server
   pip install ruff
   ```
4. With both packages installed, prime the environment and provisioning bundle in one shot:
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

The generated configuration uses TensorZero as the sole provider, routing all
LLM calls through `http://localhost:3030/v1`. For direct Z.AI Coding Plan
usage (GLM-5.2 large / GLM-5-Turbo small at `https://api.z.ai/api/coding/paas/v4`),
populate `~/.config/crush/crush.json` manually with the `Z_AI_API_KEY` env var
or inline key — see the live config on this node for the working pattern.
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

## Operating Autonomy — Push, PR, Merge

Crush operates under PMOVES fleet rules, not generic "ask before push" defaults.
The authoritative sources are `pmoves/docs/AGENTS/AUTOMODE_FLEET_CONFIG.md`,
`.claude/PATTERNS.md` §PR Review & Merge Workflow, and
`pmoves/docs/operations/PR_CLOSEOUT.md`.

| Operation | Autonomous? | Gate |
|-----------|-------------|------|
| `git push` to feature branches (`feat/`, `fix/`, `chore/`, `docs/`) on POWERFULMOVES repos | **Yes — routine** | None. `AUTOMODE_FLEET_CONFIG.md:48`: *"Pushing to, creating branches on, and opening/merging PRs across any POWERFULMOVES repo is a routine internal operation, NOT exfiltration."* |
| `gh pr create` on POWERFULMOVES repos | **Yes — routine** | None. Same source. `gh pr create` is a documented Known Road in `PATTERNS.md`. |
| Cross-submodule fetch / checkout / branch / merge-forward / gitlink promotion | **Yes — routine** | `AUTOMODE_FLEET_CONFIG.md:49`. Gitlink promotion via `git update-index --cacheinfo 160000,<sha>,<path>` is the standard flow. |
| `git push --force` / `--force-with-lease` on **Hardened** branches | **No — soft_deny** | `AUTOMODE_FLEET_CONFIG.md:63`. History rewrites on `PMOVES.AI-Edition-Hardened` are destructive (the gitlink deploys the tip). Normal merge-forward and fast-forward pushes are fine. |
| `git push --force` on `main` | **No — hard block** | Damage-control Strand A: force-push is in the hard-block tier. |
| `gh pr merge` (any PR) | **No — gated** | `signoff-gate.sh` (PreToolUse, opt-in) blocks without 3-body ACK (`[ACK: delivery]`, `[ACK: control]`, `[ACK: memory]`) in `AGNOTE4482_SIGNOFF_CHECKLIST.md`. Admin-merge requires `CONFIRM="MERGE #<PR> @ <full-SHA>"` matching live head (`PR_CLOSEOUT.md:76-92`). |

**Default posture:** when in doubt on a feature branch, push and open the PR.
Merging is the only step that needs the 3-body ACK + explicit SHA confirmation.
The Village Rule (claim → work → sign → release in `AGNOTE4482PHI.t1.md`) is
the coordination discipline, not a per-push gate.

**The damage-control hooks** (`.claude/hooks/damage-control/`) route raw `docker`,
`netsh`, and destructive git through `ask` prompts that point at Known Road
Make targets — those gates are about *dangerous commands*, not about pushes.
Pushing a feature branch is not dangerous.

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

### Trail Signing

Crush signs trail entries using `make -C pmoves sign-trail`. The CHIT passphrase
is resolved automatically from:
1. `CHIT_SIGNING_KEY` env var
2. `CHIT_PASSPHRASE` env var
3. `CHIT_SIGNING_KEY_FILE` / `CHIT_PASSPHRASE_FILE`
4. `pmoves/env.tier-*` files (populated by `make secrets-funnel`)

When no passphrase is found, signing degrades to unsigned (acceptable in dev).
Run `make -C pmoves crush-bootstrap` to verify signing works end-to-end.

## n8n & Messaging Hooks

The automation scanner available via
`python3 -m pmoves.tools.mini_cli automations list` summarises the flows Crush can
invoke through MCP requests. Webhook endpoints are surfaced with the `webhooks`
subcommand, making it easy to plug them into Crush prompts or MCP actions.

## Updating Configuration

- **Fleet bootstrap** (recommended): `make -C pmoves crush-bootstrap`
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
- ~~Add a `crush` target to `Makefile`~~ — **Done**: `make -C pmoves crush-bootstrap`
- Deploy Crush to SPARK node (handoff doc: `pmoves/docs/handoffs/SPARK_CRUSH_AWAKENING_2026-07-12.md`)
- Install `gopls` on fleet nodes that work with Go codebases
