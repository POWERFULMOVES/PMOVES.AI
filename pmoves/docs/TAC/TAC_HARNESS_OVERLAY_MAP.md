# TAC Tree: Harness Overlay Map

> Which surface each coding harness exposes for configuration and control, and which seam PMOVES overlays onto it. The map exists so that "connect or paper over?" can be answered BEFORE a launcher, generator or template is written, and cited by the reviewer afterwards.

**Status:** living map (seeded 2026-10-11, 5090-CLAUDE) · **Doctrine:** `pmoves/docs/danger-room/anti-patterns.md` § `overlay-paper-over` · **Reviewer hooks:** `.github/pull_request_template.md` overlay checkbox, `kilocode-review.yml` section 2, `pmoves-pair-review` observation class 5 · **Declared in:** `pmoves/config/agent_registry.yaml` rows with `kind: harness` (each carries an `overlay:` block) · **ACP status:** `pmoves/configs/acp_registry_map.json` (`python pmoves/tools/acp_registry_map.py`) · **Skills parity:** `make -C pmoves skills-parity`

Operator canon, 2026-10-11 (verbatim): "PMOVES connects and overlays it does not break shim or paper over this is considered anti pattern anbd should be on every pr reviewers list and should be checked before implementation which means maps are needed".

## Teachable moments, not blame

Operator, 2026-10-11 (verbatim): "the purpose is not to blame it is to learn those were honest efforts which led to a better outcome the teachable moment".

The last column of the map records where an overlay crossed its seam. Each entry names what the honest effort produced, because that is the point of recording it:

| Lane | Honest effort | Better outcome it led to |
|---|---|---|
| #3282 (Mavis launcher, regen) | one generator for every launcher trio, so no hand-copied `.ps1` drifts | this room, this map, and the rule that a generator diff which deletes lines the harness shipped is a review finding |
| #3325 (kimi `--help` regex) | make `kimi-pmoves.sh` start the program it is named for | the declared-flavor design: `kimi_code` is a registry row, the flavor on a node is a stated fact, a behaviour probe is only the refusal path |
| kilo launcher exec'ing `opencode` | one launcher for the OpenCode family | `kilo.json` at the repo root as the native surface; Kilo and OpenCode are two registry rows that share `.agents/skills` only on OpenCode's side |

## How to read a row

| Column | Meaning |
|---|---|
| **Native surface** | The harness's own settings files, flags and protocol. This is the contract. PMOVES reads and writes THROUGH it, never around it. The same facts live machine-readably in the registry row's `overlay.settings` / `overlay.instructions` / `overlay.skills_dir`. |
| **ACP** | Entry id in `pmoves/configs/acp_registry_map.json` (generated from the PMOVES-registry fork of `agentclientprotocol/registry`) and its status there. `linked` = a PMOVES registry row names the entry (`overlay.acp.registry_id`); `available` = in the registry, no PMOVES row. The registry fork's CI harness (`.github/workflows/client.py`, `verify_agents.py`) and `pmoves/tools/acp_launcher_probe.py` speak the handshake; do not hand-roll one (`hand-rolled-launch-verify`). |
| **PMOVES overlay seam** | What PMOVES is allowed to layer: identity (node pins, CHIT), env (`env.shared`, model-suit selection), MCP roster, fleet routing. Anything else is a paper-over until this row says otherwise. |
| **Launcher** | The script that performs the overlay today. Generator-emitted launchers live under `deploy/provision/` and are regenerated from `pmoves/configs/cli_tools.yaml` + `agent_registry.yaml`; hand-written ones are `managed_by: hand` in `launchers.manifest.json`. |
| **Teachable moment on record** | Measured places where the overlay crossed the seam, and what each taught. Each one is a review finding, a Danger Room room, or both. |

Cells marked **unmapped** are honest gaps (Emperor-CHIT-Humility): nobody has written the native surface down yet, so a PR touching that harness must map it first and add the row.

## The map

| Harness | Native surface | ACP | PMOVES overlay seam | Launcher | Teachable moment on record |
|---|---|---|---|---|---|
| **Claude Code** (`claude_code`) | `~/.claude/settings.json` < `.claude/settings.json` < `.claude/settings.local.json` < `--settings` < managed; permission lists MERGE across scopes (a local allow cannot lift a project deny). `--mcp-config <file>`, `--agent`, `--append-system-prompt` (last occurrence wins). Skills: `.claude/skills/` only; it does not read the cross-agent `.agents/skills/` (docs read 2026-10-11). `.claude/mcp.json` is the PMOVES roster, read from `origin/main` by the launcher. | `claude-acp` 0.79.0, **`linked`** → `claude_code` | identity via `--agent` + node vocabulary; env via `env.shared`; MCP via normalized roster passed with `--mcp-config=`; cipher per-agent id. | `deploy/provision/claude-pmoves.sh` (hand, FAIL-CLOSED roster per #2847/#2809); `pmoves/scripts/claude-pmoves.sh` is a thin delegate adding the positional agent | #3282 regen changed the 5090 `.ps1` resolver and committed `configs/claude_settings/minimax.json` with an operator home path (still on main 2026-10-11). Taught: a generator that owns every trio must diff against what the harness shipped, not only against its own last output. |
| **Crush** | `crush.json` written by `crush_configurator.py`; no `--append-system-prompt`, so context arrives through an identity file the configurator lists. Skills: `.crush/skills/` (project), `~/.config/crush/skills` (global). Fail-open rule documented in the launcher. | not in registry (2026-10-11) | identity file + CHIT; MCP via configurator (mirrors `mcp_inventory.json`); `Z_AI_API_KEY → ZAI_API_KEY` name bridge. | `pmoves/scripts/crush-pmoves` (hand) | none recorded; the cipher transport change (#3339) went through the configurator, which is the seam. |
| **Codex** (`codex_cli`) | `~/.codex/config.toml` (`$CODEX_HOME`); project-scoped `.codex/config.toml` is loaded ONLY when the project is trusted (`projects.<path>.trust_level`) and ignores provider, profile and base-URL keys. `--profile <name>` selects `$CODEX_HOME/<name>.config.toml`; `-c key=value` overrides. MCP: `[mcp_servers.<id>]` with `command`/`args`/`url`/`env`/`enabled`/`required`. Instructions: `AGENTS.md` read natively (`project_doc_max_bytes`, `project_doc_fallback_filenames`, `model_instructions_file`). Skills: `.agents/skills/` + `~/.codex/skills`, per-skill `skills.config[].path`/`enabled`. (Codex config reference, read 2026-10-11.) | `codex-acp` 1.12.0, **`linked`** → `codex_cli` | env.shared only today; launcher is `exec codex "$@"`. **Integration point to wire:** the PMOVES roster as `[mcp_servers.*]` in a trusted-project `.codex/config.toml`, generated from `.claude/mcp.json` the way `crush_configurator.py` does for Crush. Follow-up lane. | `pmoves/scripts/codex-pmoves.sh`; generated trio under `deploy/provision/` | #3282 regen replaced the blocklist regex and the `.ps1` character-arithmetic regex (kilo review, unanswered). Taught: hydrate through `config.toml`, do not reach for a wrapper flag. |
| **Kilo / OpenCode** (`kilocode_glm`, `opencode`) | OpenCode MERGES config sources in order: remote `.well-known/opencode` < `~/.config/opencode/opencode.json` < `$OPENCODE_CONFIG` < project `opencode.json` < `.opencode/` dirs < `$OPENCODE_CONFIG_CONTENT` < managed (docs read 2026-10-11). MCP under the `mcp` key. Skills: `.agents/skills/` (OpenCode). Kilo is the maintained fork: `kilo.json` at the repo root, skills in `.kilocode/skills/` (24 tracked `kilocode-*` skills today). | `kilo` 7.7.5 **`linked`** → `kilocode_glm`; `opencode` 1.18.31 **`linked`** → `opencode` | per-node claws config was passed with `--config`, a flag neither program has; the seam is `kilo.json` / `OPENCODE_CONFIG`; `Z_AI_API_KEY → ZAI_API_KEY` bridge; `PMOVES_NODE_ID` pin. | `pmoves/scripts/kilo-pmoves.sh`; generated trio | main's launcher exec's `opencode`, not `kilo`; #3325 corrects the binary. #3282 regen deleted the name bridge from `deploy/provision/kilo-pmoves.sh` (kilo review). Taught: two programs, two registry rows, two skills dirs; one launcher cannot serve both by guessing. |
| **Kimi** (`kimi_code`) | Two programs share the command name. **Kimi Code CLI** (current; install script / npm; speaks ACP via `kimi acp`; MCP managed in-session with `/mcp-config`): `${KIMI_CODE_HOME:-~/.kimi-code}/{config.toml,mcp.json}`; skills `.agents/skills/`. **Archived kimi-cli** (Python, MoonshotAI/kimi-cli, "replaced by Kimi Code CLI" per its README): `--config-file`, `--mcp-config-file`, `~/.kimi/`; the repo's `.kimi/` dir (`config.toml`, `mcp.json`, a 125-line `AGENTS.md`, `skills/pmoves-kimi-bootstrap`) is THIS surface. Flavor on a node is an operator fact, not a runtime inference. | `kimi` (Kimi CLI 1.50.0) `available`, **deliberately not bridged**: that registry entry pins the archived binary archive. `kimi_code` carries `overlay.acp.registry_id: null` until a `kimi-code/agent.json` lands upstream (registry PR). `PMOVES-ClawZ/acp-router` already maps `kimi → agentId: "kimi"`. | `.kimi/AGENTS.md` + bootstrap skill; declare flavor in `node-vocabulary.yaml` (`default_identity.kimi` exists; a flavor key does not yet). | `pmoves/scripts/kimi-pmoves.sh`; generated trio | #3325: launcher greps `kimi --help` for `--config-file` to pick the program; two regex rounds (2026-10-10, 2026-10-11) and it still infers from prose. Taught: the registry row + a declared flavor replace the probe; keep a behaviour probe only as the refusal path. |
| **Hermes** | `hermes --profile <name>`; profiles under `pmoves/config/nats/hermes/` and `pmoves/config/profiles/hermes/`; `make hermes-bootstrap` writes profile + MCP + CHIT. Skills: `.hermes/skills/` (project), `$HERMES_HOME/skills` (global). | not in registry (2026-10-11) | profile selection (`PMOVES_HERMES_PROFILE`, default `pmoves-hermes-elder`); MCP + CHIT via bootstrap. | `pmoves/scripts/hermes-pmoves` (hand) | none recorded. |
| **Agent Zero** | Supervisor REST on 8080 (`/mcp/execute`, `/tasks`, `/sessions`); runtime MCP on 8081 at `/t-{token}/{sse,http,messages}`; plugins vendored in `PMOVES-a0-plugins/plugins/`. | `a0_acp` plugin exposes A0 as an ACP stdio agent | plugins are the seam: `pmoves_coding_agents` (delegates to hermes/crush/opencode/codex headless, CHIT-signed), `kimi_code` + `kilo_code_gateway` + `codex_provider` (providers), `jev_router` (TypeSafe Jev auto-routing + telemetry), `typesafe_ai` (typed Jev questions). Compose + env via `pmoves/docker-compose*.yml`. | `make -C pmoves up-a0-archon-scoped SERVICES=agent-zero`; no CLI launcher | `PMOVES-a0-plugins/PMOVES.AI_INTEGRATION.md` "PMOVES Overlay Surface" is still `_TBD_` on every line; Jev plugins are vendored but undocumented in the living docs (follow-up lane); the open-weight Jev reproductions the plugins could point at are recorded in the Jev landscape issue #3360 (2026-10-11), not here. |

## Skills seam: parity across AGInTZ

Operator, 2026-10-11 (verbatim): "https://github.com/POWERFULMOVES/PMOVES-skills https://github.com/POWERFULMOVES/PMOVES-agents.md needs to be resolved at root which means parrity across AGInTZ skills cant only work for one".

Each harness reads its own project-level skills directory and none reads another's. The directories, from the agent table in the PMOVES-skills fork (`skills/PMOVES-skills/src/agents.ts`, vercel-labs/skills, read 2026-10-11) and re-derived live by `pmoves/tools/skills_parity.py`:

| Harness | Project skills dir | Global skills dir | In this checkout (2026-10-11) |
|---|---|---|---|
| Claude Code | `.claude/skills/` | `~/.claude/skills` | 36 skills, the canonical set |
| Codex | `.agents/skills/` | `$CODEX_HOME/skills` | absent |
| OpenCode | `.agents/skills/` | `~/.config/opencode/skills` | absent |
| Kimi Code CLI | `.agents/skills/` | `~/.agents/skills` | absent; `.kimi/skills/` holds one legacy-surface skill |
| Kilo | `.kilocode/skills/` | `~/.kilocode/skills` | 24 `kilocode-*` skills, none shared with the canonical set by name |
| Crush | `.crush/skills/` | `~/.config/crush/skills` | absent |
| Hermes | `.hermes/skills/` | `$HERMES_HOME/skills` | absent |

So today a PMOVES skill works for exactly one AGInT. The resolution at root:

1. **Report before gate.** `make -C pmoves skills-parity` prints the matrix above against the live tree; `--strict` turns it into a CI gate once the seam is wired. It is warn-only until then, so the gap is visible without a red build.
2. **Project, do not fork.** The PMOVES-skills CLI is the sanctioned projector: it installs one skill into every agent directory (copy mode or symlink mode). The canonical tree stays `.claude/skills/`; the other six directories are projections.
3. **Projections are generated, not tracked.** Git symlinks fail on Windows checkouts (this session measured `Can't create the symlink` on three worktree operations), and tracked copies drift. Add the six projection dirs to `.gitignore` and regenerate them in each `*-pmoves` launcher's bootstrap step, the same way `crush_configurator.py` regenerates `crush.json`. `.kilocode/skills/` is the exception: its 24 skills are Kilo-only content and stay tracked.
4. **Instructions resolve at root too.** `AGENTS.md` at the repo root (agents.md format, read natively by Codex and by the ACP-era CLIs) is the one instruction surface; `.kimi/AGENTS.md` is a 125-line fork of it and should become a pointer. `PMOVES-agents.md/` is the format spec fork and carries no PMOVES content (`.claude/CLAUDE.md` Tier 2 note).

Items 2 to 4 are the follow-up lane; item 1 lands with this map.

## Identity outlives the node

Operator, 2026-10-11 (verbatim): "PMOVES.AI cannot be dependant on missing agint or node that is what resilience is for the AGInTZ here are persisted for that very reason this way node can be replaced you still have AGInT with identity however what is important is the trace and the artifacts the embeds once we register proper it will be on public blockchains so we need to prep for that".

What already carries this, and what is still null:

- **Identity is persisted in the registry, not on the node.** `pmoves/config/signing_identity_cards.yaml` holds 31 cards: per-harness identities (`codex`, `kilocode`, `crush`, `hermes`, `gemini`, `cline`) and node-worn Claude identities (`4090-claude`, `5090-claude`, `z890-claude`, `b850-claude`, `spark-claude`). A node can be replaced; the card, its glyph and its role survive it. The harness rows added here are the same move for the harnesses themselves.
- **The trace is the product.** The CHIT-signed Graphiti trail (`make -C pmoves sign-trail`), the Cipher memory store (the embeds), and the claim register are the artifacts that outlive a session. The machine half of every card (`ml.*` key fields) is still null and the trail's `signing_card_id` tie is pending in `signature.v2.schema.json`.
- **Blockchain prep means two things now, not a rewrite later:** every trail entry and artifact must be content-addressed (hash in the record) and signed by a card whose public half can be published. Until the `ml` halves land, the trail is attributable but not externally verifiable; that is the gap a public-chain anchor would expose, so close it first.

## Adding a row

1. Read the harness's own docs for its settings precedence and flags (`feedback_read_upstream_docs_first`). Write the native surface cell from those docs, with the version and the read date.
2. Add a `kind: harness` row to `pmoves/config/agent_registry.yaml` with an `overlay:` block (`acp`, `settings`, `instructions`, `skills_dir`, `launcher`) and put it in a team in `agent-teams.yaml`; the registry gate (`validate_agent_registry.py`) refuses an orphan.
3. Look the harness up in `acp_registry_map.json`; if it is `available`, add the bridge to `EXPLICIT_BRIDGES` in `acp_registry_map.py` and regenerate. If the registry entry pins a different program than the one PMOVES runs (the `kimi` case), do not bridge it; the bridge is a registry PR.
4. State the overlay seam as the four allowed layers only. If the change needs a fifth, that is a doctrine change: bring it to the operator, do not slip it into a launcher.
5. Add the harness to `PINNED_DIRS` in `skills_parity.py` if the PMOVES-skills agent table has it. Cite the row in the PR body and tick the overlay checkbox.
