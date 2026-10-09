# Kilo CLI Harness — PMOVES-KeYlOkODe Wiring

> Status: **canonical** (2026-09-14). Owner: KiloClaw instance.
> Scope: what the `PMOVES-KeYlOkODe` submodule is, how the Kilo CLI fits the
> fleet harness, and the deploy/review contract for the fork.

## TL;DR

`POWERFULMOVES/PMOVES-KeYlOkODe` is the PMOVES fork of **Kilo CLI upstream**
(`Kilo-Org/kilocode`, package `@kilocode/cli`, currently **v7.6.2**, the
2026-09-10 release). It is tracked as a git submodule at
`PMOVES-KeYlOkODe/` and is the **CLI harness source of truth** for every
node that runs Kilo Code — 5090, laptop-4090, z890, and the hosted
KiloClaw VPS.

The fork's CLI reads this repo's `kilo.json` **natively** (config discovery:
`kilo.json` / `opencode.json` in project root, `.kilo/` dirs, ancestor walk —
see fork `specs/v2/config.md`). No wrapper indirection is required to pick up
the model pin, providers, MCP servers, or skills paths.

## Why it was not in PMOVES.AI before

- The fork existed as a standalone repo; PMOVES.AI only referenced KiloCode
  indirectly (`opencode-<node>.json` configs + `kilo-pmoves` wrapper + the
  `kilocode-project` service entry pointing at bare `kilo.json`).
- Nothing pinned the fork version, so config drift was undetectable.
- The repo's `kilo.json` had drifted from the runtime lane: it pinned
  `zai/glm-5.2` while the hosted KiloClaw VPS runs
  `kilocode/zai-coding/glm-5.3`, and the plan-routed overflow provider
  (`kilocode` → `api.kilocode.ai`) was not declared at all.

## What this wiring adds

| Surface | Change |
|---|---|
| `PMOVES-KeYlOkODe/` | Submodule added (fork of `Kilo-Org/kilocode`, tracks `main`) |
| `kilo.json` | Model pin `zai/glm-5.2` → `zai/glm-5.3` (flagship suit); `kilocode` provider lane added (plan-routed `kilo-auto/balanced`); corrupted Supabase MCP args line repaired (stray duplicate args block with a literal U+2026 char) |
| `pmoves/configs/cli_tools.yaml` | `kilo` host CLI entry (install/check); `keylokode-fork` service entry; `kilocode-project` purpose refreshed |
| `pmoves/configs/agent-profiles/kiloclaw.yaml` | `kiloclaw` VPS seat added to `node_affinity`; `runtime_model: kilocode/zai-coding/glm-5.3` documented; fork pointer in header |
| `pmoves/configs/model-suits/kilocode-zai-coding-glm-5.3.yaml` | New suit for the live plan-routed GLM-5.3 lane |
| `pmoves/config/provider_catalog.yaml` | `kilocode.chat_kilocode_zai_glm53` entry (`zai-coding/glm-5.3`, role primary 0.7 on `coding_kilocode`) |
| `pmoves/config/agent_registry.yaml` | New `kiloclaw` harness entry (node_affinity + `kiloclaw` VPS, `ci_runner: vps`) |
| `AGENTS.md` | Canonical doc row: `pmoves/docs/operations/KILO_CLI_HARNESS.md` |

## Model lane map (grounded)

| Lane | Model id | Surface | Suit |
|---|---|---|---|
| KiloClaw VPS runtime | `kilocode/zai-coding/glm-5.3` | Kilo CLI session model (this VPS) | `kilocode-zai-coding-glm-5.3.yaml` |
| Kilo CLI default (repo) | `zai/glm-5.3` | `kilo.json` `model` | `glm-5.3.yaml` |
| Z.AI direct | `glm-5.3` / `glm-5-turbo` / `glm-5.1` | provider catalog `zai` | existing suits |
| Plan-routed overflow | `kilo-auto/balanced` | `kilocode` provider (OpenRouter-style) | `kilo-auto-balanced.yaml` |
| KiloClaw profile wire target | `glm-5.1` | `kiloclaw.yaml` harness dispatch | `glm-5.1.yaml` |

Note on IDs: the Kilo CLI's `parseModel` splits on the **first** slash —
`kilocode/zai-coding/glm-5.3` = provider `kilocode`, model
`zai-coding/glm-5.3`. The fork's provider `whitelist` filter is **exact-match**
(`Array.includes`), not glob — `kilo.json` whitelists the full literal id.

## Version pinning and upgrades

- Upstream: `Kilo-Org/kilocode` — check latest with
  `gh api repos/Kilo-Org/kilocode/releases/latest --jq .tag_name`.
- Fork: `POWERFULMOVES/PMOVES-KeYlOkODe` (fast-track upstream; fork-only
  commits land via Kilo's own docs-sync/quality automations).
- Upgrade drill:
  1. Bump the submodule pointer (`git submodule update --remote PMOVES-KeYlOkODe`).
  2. Diff `kilo.json`-relevant config surface against fork
     `specs/v2/config.md` + `specs/v2/schema-changelog.md` (v2 spec is the
     authority for what config keys are ported/redesigned/removed — e.g.
     `small_model` and `default_agent` are slated for removal in v2; when
     that lands, migrate `kilo.json` accordingly).
  3. Re-validate JSON (`python3 -c "import json;json.load(open('kilo.json'))"`)
     and YAML configs, then `git add` the submodule bump as its own commit.
- ACP registry parity: `POWERFULMOVES/PMOVES-registry` (`kilo/agent.json`)
  is already pinned to **7.6.2** = latest upstream release — no action needed
  this pass; recheck on every fork bump.

## Skills deploy path

- PMOVES-skills (`vercel-labs/skills` fork) discovers Kilo at
  `.kilocode/skills` / `~/.kilocode/skills` — this remains correct: the
  7.6.x fork **still scans legacy `.kilocode/`** alongside canonical
  `.kilo/` (fork `packages/opencode/src/kilocode/docs/migration.md`).
- This repo ships PMOVES skills in `.kilocode/skills/` (gitignored except
  rules/skills) and agent/command definitions in `.kilo/agent/` +
  `.kilo/command/` (tracked). Both layouts load under 7.6.x.
- When the v2 scanner drops legacy `.kilocode/` support, migrate the
  `skills.paths` entry in `kilo.json` and re-point PMOVES-skills
  `src/agents.ts` (`kilo.skillsDir`) in the same commit.

## Deploy posture

- **KiloClaw VPS (this instance)**: Kilo CLI is preinstalled and pinned by
  the platform (`/root/.config/kilo/kilo.json`, currently
  `kilo/ollama-cloud/glm-5.2` local shim config — the KiloCode
  plan-routed lane `kilocode/zai-coding/glm-5.3` is the session-model
  override lane). Repo-level work inside PMOVES.AI uses the repo
  `kilo.json` config contract; do not hand-edit the platform config.
- **5090 / laptop-4090 / z890**: install `@kilocode/cli` (see
  `cli_tools.yaml` → `host_clis.kilo`), then `kilo` inside the repo picks
  up `kilo.json` automatically. The legacy `kilo-pmoves` +
  `opencode-<node>.json` path stays for OpenCode-runtime nodes.
- **Review gates**: changes to `kilo.json`, `cli_tools.yaml`,
  `provider_catalog.yaml`, `agent_registry.yaml`, or the submodule pointer
  should ride together in one PR (they are one logical wiring unit) and
  must keep `provider_catalog.yaml` + `agent_registry.yaml` YAML-lint
  clean (`python3 -c "import yaml;yaml.safe_load(open(...))"`).

## Verification log (2026-09-14)

- Fork clone: `PMOVES-KeYlOkODe` @ `5042e966` — head matches upstream
  v7.6.2 tag window (2026-09-14 commits on top of 2026-09-10 release).
- `kilo.json` parses; model = `zai/glm-5.3`; providers = zai, kilocode,
  minimax; Supabase args repaired to `["npx","-y","@supabase/mcp-server-postgrest@0.1.1","--apiUrl",...,"--schema","public"]`.
- `provider_catalog.yaml`, `agent_registry.yaml`, `cli_tools.yaml`,
  model suits, agent profiles: `yaml.safe_load` PASS.
- Upstream release check: v7.6.2 (2026-09-10) — registry `kilo/agent.json`
  already current.
