# TAC Tree: Harness Overlay Map

> Which surface each coding harness exposes for configuration and control, and which seam PMOVES overlays onto it. The map exists so that "connect or paper over?" can be answered BEFORE a launcher, generator or template is written, and cited by the reviewer afterwards.

**Status:** living map (seeded 2026-10-11, 5090-CLAUDE) · **Doctrine:** `pmoves/docs/danger-room/anti-patterns.md` § `overlay-paper-over` · **Reviewer hooks:** `.github/pull_request_template.md` overlay checkbox, `kilocode-review.yml` section 2, `pmoves-pair-review` observation class 5

Operator canon, 2026-10-11 (verbatim): "PMOVES connects and overlays it does not break shim or paper over this is considered anti pattern anbd should be on every pr reviewers list and should be checked before implementation which means maps are needed".

## How to read a row

| Column | Meaning |
|---|---|
| **Native surface** | The harness's own settings files, flags and protocol. This is the contract. PMOVES reads and writes THROUGH it, never around it. |
| **ACP** | Entry id in `pmoves/configs/acp_registry_map.json` (generated from the PMOVES-registry fork of `agentclientprotocol/registry`) and its status there. `linked` = a PMOVES agent references the repo; `available` = in the registry, not yet bridged. The registry fork ships `client.py` (initialize → session/new → auth probe), `verify_agents.py` and `registry_utils.py`; speak ACP through those, do not hand-roll a handshake (`hand-rolled-launch-verify`). |
| **PMOVES overlay seam** | What PMOVES is allowed to layer: identity (node pins, CHIT), env (`env.shared`, model-suit selection), MCP roster, fleet routing. Anything else is a paper-over until this row says otherwise. |
| **Launcher** | The script that performs the overlay today. Generator-emitted launchers live under `deploy/provision/` and are regenerated from `pmoves/configs/cli_tools.yaml` + `agent_registry.yaml`; hand-written ones are `managed_by: hand` in `launchers.manifest.json`. |
| **Overreach on record** | Measured places where the overlay crossed the seam. Each one is a review finding, a Danger Room room, or both. |

Cells marked **unmapped** are honest gaps (Emperor-CHIT-Humility): nobody has written the native surface down yet, so a PR touching that harness must map it first and add the row.

## The map

| Harness | Native surface | ACP | PMOVES overlay seam | Launcher | Overreach on record |
|---|---|---|---|---|---|
| **Claude Code** | `~/.claude/settings.json` < `.claude/settings.json` < `.claude/settings.local.json` < `--settings` < managed; permission lists MERGE across scopes (a local allow cannot lift a project deny). `--mcp-config <file>`, `--agent`, `--append-system-prompt` (last occurrence wins). `.claude/mcp.json` is the PMOVES roster, read from `origin/main` by the launcher. | `claude-acp` 0.77.0, `available` | identity via `--agent` + node vocabulary; env via `env.shared`; MCP via normalized roster passed with `--mcp-config=`; cipher per-agent id. | `deploy/provision/claude-pmoves.sh` (hand, FAIL-CLOSED roster per #2847/#2809); `pmoves/scripts/claude-pmoves.sh` is a thin delegate adding the positional agent | #3282 regen changed the 5090 `.ps1` resolver and committed `configs/claude_settings/minimax.json` with an operator home path (still on main 2026-10-11). |
| **Crush** | `crush.json` written by `crush_configurator.py`; no `--append-system-prompt`, so context arrives through an identity file the configurator lists. Fail-open rule documented in the launcher. | not in registry (2026-10-11) | identity file + CHIT; MCP via configurator (mirrors `mcp_inventory.json`); `Z_AI_API_KEY → ZAI_API_KEY` name bridge. | `pmoves/scripts/crush-pmoves` (hand) | none recorded; the cipher transport change (#3339) went through the configurator, which is the seam. |
| **Codex** | `~/.codex/config.toml`, env-driven auth (`OPENAI_*`, `CODEX_*` on the generator blocklist). **unmapped:** which keys the launcher should hydrate. | `codex-acp` 1.11.0, `available` | env.shared only today; launcher is `exec codex "$@"`. | `pmoves/scripts/codex-pmoves.sh`; generated trio under `deploy/provision/` | #3282 regen replaced the blocklist regex and the `.ps1` character-arithmetic regex (kilo review, unanswered). |
| **Kilo / OpenCode** | Kilo ships as `kilo` (same project as `kilocode` in `agent_registry.yaml`); per-node config at `pmoves/configs/claws/opencode-<node>.json` passed with `--config`. | `kilo` 7.6.2 **`linked`** → `kilocode_glm`; `opencode` 1.18.30 `available` | per-node claws config via `--config`; `Z_AI_API_KEY → ZAI_API_KEY` bridge; `PMOVES_NODE_ID` pin. | `pmoves/scripts/kilo-pmoves.sh`; generated trio | main's launcher exec's `opencode`, not `kilo`; #3325 corrects the binary. #3282 regen deleted the name bridge from `deploy/provision/kilo-pmoves.sh` (kilo review). |
| **Kimi** | Two programs share the name. Kimi Code: `${KIMI_CODE_HOME:-~/.kimi-code}/{config.toml,mcp.json}` + project `.mcp.json`. Legacy kimi-cli: `--config-file`, `--mcp-config-file`, repo `.kimi/`. Flavor is an operator fact per node, not a runtime inference. | `kimi` (Kimi CLI 1.50.0), `available` | `.kimi/AGENTS.md` + bootstrap skill; `PMOVES-ClawZ/acp-router` already maps `kimi → agentId: "kimi"`. Declare flavor in `node-vocabulary.yaml` (`default_identity.kimi` exists; a flavor key does not yet). | `pmoves/scripts/kimi-pmoves.sh`; generated trio | #3325: launcher greps `kimi --help` for `--config-file` to pick the program; two regex rounds (2026-10-10, 2026-10-11) and it still infers from prose. Replace with a declared flavor; keep a behaviour probe only as the refusal path. |
| **Hermes** | `hermes --profile <name>`; profiles under `pmoves/config/nats/hermes/` and `pmoves/config/profiles/hermes/`; `make hermes-bootstrap` writes profile + MCP + CHIT. | not in registry (2026-10-11) | profile selection (`PMOVES_HERMES_PROFILE`, default `pmoves-hermes-elder`); MCP + CHIT via bootstrap. | `pmoves/scripts/hermes-pmoves` (hand) | none recorded. |
| **Agent Zero** | Supervisor REST on 8080 (`/mcp/execute`, `/tasks`, `/sessions`); runtime MCP on 8081 at `/t-{token}/{sse,http,messages}`; plugins vendored in `PMOVES-a0-plugins/plugins/`. | `a0_acp` plugin exposes A0 as an ACP stdio agent | plugins are the seam: `pmoves_coding_agents` (delegates to hermes/crush/opencode/codex headless, CHIT-signed), `kimi_code` + `kilo_code_gateway` + `codex_provider` (providers), `jev_router` (TypeSafe Jev auto-routing + telemetry), `typesafe_ai` (typed Jev questions). Compose + env via `pmoves/docker-compose*.yml`. | `make -C pmoves up-agent-zero`; no CLI launcher | `PMOVES-a0-plugins/PMOVES.AI_INTEGRATION.md` "PMOVES Overlay Surface" is still `_TBD_` on every line; Jev plugins are vendored but undocumented in the living docs (follow-up lane). |

## Jev, briefly

TypeSafe Jev (`jev-1.13.0`) is already the stage-2 secret detector for the chat corpus (`pmoves/chat-corpus/SPOTAUDIT.md`, `RECALL_SUITE.md`), and Agent Zero carries two Jev plugins (`jev_router`, `typesafe_ai`). Neither appears in `.claude/CATALOG.md`, `LIVING_DOCS_INDEX.md` or the A0 integration dossier yet. That sweep is the follow-up to this map, after #3345 (SPARK-CLAUDE's topology walk) lands, so the two lanes do not edit `TAC_INTEGRATION_TOPOLOGY.md` at once.

## Adding a row

1. Read the harness's own docs for its settings precedence and flags (`feedback_read_upstream_docs_first`). Write the native surface cell from those docs, with the version.
2. Look the harness up in `acp_registry_map.json`; if it is `available`, the bridge is a registry PR, not a wrapper.
3. State the overlay seam as the four allowed layers only. If the change needs a fifth, that is a doctrine change: bring it to the operator, do not slip it into a launcher.
4. Cite the row in the PR body and tick the overlay checkbox.
