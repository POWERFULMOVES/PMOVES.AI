# PMOVES Combined Pinokio Customization — Design

**Date:** 2026-07-20
**Author:** z890-claude (z890-infra alter)
**Status:** Design approved (operator verbal), pending written-spec review
**Related tasks:** #11 (pbnj→submodule), #13 (PMOVES-claude-code), #14 (this design)

## Goal

Make **PMOVES-pinokio** the single combined home for every PMOVES Pinokio customization (launchers + super-customized code agents), while each service-owned customization *also* lives in its own fork ("we can have both"), with no drift between the combined copy and the source.

## Motivation

`pbnj/` is 80 loose tracked files in the meta-repo with no `.gitmodules` entry — drift from the fork-as-submodule fleet pattern. Meanwhile Crush established a **distributed** pattern (`pmoves-crush` launcher lives inside PMOVES-crush). The operator wants both models reconciled: a combined aggregator fork *and* per-service ownership. This design is the reconciliation.

## Constraints discovered (load-bearing)

1. **Claude Code's CLI is a closed npm bundle** (`@anthropic-ai/claude-code`). The public `anthropics/claude-code` repo (which seeded PMOVES-claude-code) is the *extension surface* — `plugins/`, `examples/`, `.claude-plugin/`, `.devcontainer/`, `scripts/` — **not** forkable CLI source like Crush's Go. So "full fork + integration like Crush" lands as **deep integration via the extension surface + Agent SDK**, not CLI-internal patching.
2. **`plugin/code` is upstream `pinokiocomputer/code`, unmodified** (verified: remote = `https://github.com/pinokiocomputer/code`, clean tree). The `claude` plugin just runs `npx -y @anthropic-ai/claude-code@latest`. Super-customizing it requires *forking* that upstream, then repointing the `claude` plugin at PMOVES-claude-code.
3. **The meta-repo is the source of truth today** — the running `D:\pinokio` install symlinks `api/pmoves-*` back to `/d/PMOVES.AI/PMOVES.AI/pbnj/pinokio/api/*`.
4. **Sets are disjoint** — the meta-repo `pbnj/pinokio/api` has 10 launchers and *no* `pmoves-crush`; Crush's launcher only exists in PMOVES-crush. So aggregation adds, it does not collide.

## Repos and responsibilities

| Repo | Owns | Notes |
|------|------|-------|
| **PMOVES-pinokio** (fork of the Pinokio app) | The combined home: Pinokio app + launcher-only apps in-tree + submodule refs to service-owned launchers and the code-plugin collection | branch `PMOVES.AI-Edition-Hardened`; default `main` |
| **PMOVES-crush** | `pmoves-crush` launcher (already shipped, commit a64d0fc1) + the Crush Go fork | Distributed source of truth |
| **PMOVES-claude-code** | `pmoves-claude-code` launcher + deep integration (plugins/skills/hooks/subagents/MCP on the Agent SDK) | Standalone repo seeded from anthropics/claude-code; exists now |
| **POWERFULMOVES/code** (new fork of `pinokiocomputer/code`) | The code-plugin collection; `claude` plugin repointed at PMOVES-claude-code | To be created |
| **PMOVES.AI** (meta-repo) | `pbnj/` becomes one submodule → PMOVES-pinokio | Replaces 80 loose files |

## Aggregation model — Model A (submodule aggregation)

PMOVES-pinokio carries:
- **In-tree** the launcher-only apps that have no service home: `pmoves-pbnj`, `pmoves-remote`, `pmoves-services`, `pmoves-agent-zero`, `pmoves-cipher-beats`, `pmoves-discord-bot`, `pmoves-holographic-blocks`, `pmoves-model-registry`, `pmoves-model-selector`, `pmoves-notebooklm` (the 10 from the verified split).
- **As submodules** the service-owned ones and the plugin collection:
  - `api/pmoves-crush` → PMOVES-crush
  - `api/pmoves-claude-code` → PMOVES-claude-code
  - `plugin/code` → POWERFULMOVES/code (fork of pinokiocomputer/code)

Each service-owned launcher lives in its own repo **and** is referenced by the combined fork via a submodule pin — no copies, no drift; updating a launcher = bump one gitlink.

**Phase-1 boundary (deliberate):** only `pmoves-crush` and `pmoves-claude-code` are submoduled now, because they are the launchers actively owned/customized in their own repos. `pmoves-agent-zero` and `pmoves-remote` *do* have service repos (PMOVES-Agent-Zero, PMOVES-Remote-View) but their launchers currently live only in the meta-repo split, so they stay in-tree this phase and can migrate to submodules later without reshaping the topology. The rule "service-owned launcher → submodule" holds; we apply it where a service has actually claimed its launcher.

### Topology

```
PMOVES-pinokio (combined fork)
├── main.js, package.json …          # upstream Pinokio app
├── api/
│   ├── pmoves-{pbnj,remote,services,agent-zero,cipher-beats,
│   │   discord-bot,holographic-blocks,model-registry,
│   │   model-selector,notebooklm}    # launcher-only, in-tree
│   ├── pmoves-crush        → submodule → PMOVES-crush
│   └── pmoves-claude-code  → submodule → PMOVES-claude-code
└── plugin/
    └── code                → submodule → POWERFULMOVES/code (claude→PMOVES-claude-code)

PMOVES.AI meta-repo
└── pbnj  → submodule → PMOVES-pinokio        (nested submodules underneath)
```

## PMOVES-claude-code deep-integration surface

Built on the Claude Agent SDK, layered into the repo (not CLI patches):
- **Hooks** — AGENT_TRAIL emission + CHIT signing on tool events.
- **MCP servers** — PMOVES MCP wiring (cipher, docker, tailscale, agent-zero) pre-registered.
- **Skills / subagents** — PMOVES skill constellation + agent taxonomy.
- **Settings + devcontainer** — PMOVES-context defaults, model routing.
- **Pinokio launcher** (`pmoves-claude-code`) — bootstraps claude-code with the above, mirroring the crush launcher's "full PMOVES context" bootstrap.

## Build / migration sequence (each its own atomic PR)

1. **POWERFULMOVES/code**: fork `pinokiocomputer/code`; customize the `claude` plugin to launch PMOVES-claude-code; add `PMOVES.AI-Edition-Hardened`.
2. **PMOVES-claude-code**: add the deep-integration surface + `pmoves-claude-code` Pinokio launcher.
3. **PMOVES-pinokio**: land the 10 launcher-only apps in-tree (from verified branch `pinokio-hardened-merge`); add the 3 submodules.
4. **Meta-repo**: `git rm -r pbnj/`; add `pbnj` submodule → PMOVES-pinokio; fix path refs (`pbnj/pinokio/api/*` → `pbnj/api/*`) in `deploy/runbooks/pinokio-pbnj-install.md` and `.hermes/plans/2026-07-10_pmoves-p8-launcher-mesh-plan.md`.
5. **Install**: point `D:\pinokio` at PMOVES-pinokio so the running node *is* the combined fork.

## Verified during design (resolutions)

- **Pinokio submodule recurse — RESOLVED by design, not dependency.** Rather than rely on Pinokio cloning `--recurse-submodules`, each submoduled launcher's `install.js` runs an explicit `git submodule update --init --recursive`. Model A then works regardless of Pinokio's clone behavior. (Deep-grepping the Pinokio bundle for its clone logic timed out on the bundled runtime; the explicit-init approach makes the answer moot.)
- **"auto cli" — RESOLVED.** `D:\pinokio\prototype\system\cli` is Pinokio's built-in **CLI App Launcher generator**: `installable/` (custom install + launch command) and `instant/` (launch-only). `claude-code` and `crush` are CLI apps, so the plan uses the `installable` auto-cli generator to scaffold their launchers natively instead of hand-rolling `start.js`/`install.js`.

## Still verify during planning

- **Relative paths**: the `../../pmoves` paths in launcher `start.js`/`install.js` resolve against the Pinokio *install* layout (`D:\pinokio`), not the meta-repo mirror — verify they still resolve after the `pbnj/pinokio/api/*` → `pbnj/api/*` move.

## Testing / validation

- Each launcher installs + runs from the combined fork in a clean Pinokio.
- The `claude` plugin launches the PMOVES-claude-code integration (AGENT_TRAIL/CHIT active), **not** vanilla `npx @anthropic-ai/claude-code`.
- `pmoves-crush` still installs/runs from its own repo unchanged (distributed path intact).
- Meta-repo `git submodule status --recursive` resolves `pbnj` and its nested submodules.

## Out of scope

- The container-triage track (tensorzero/CHIT/edge-fn/vector) and Health/Wealth bring-up — separate workstreams.
- Rewriting the Pinokio app itself (we track upstream).
- Reimplementing the Claude Code CLI (closed bundle; extension surface only).

## Preserved artifact

Worktree `D:/PMOVES.AI/pmoves-pbnj-submodule`, branch `pinokio-hardened-merge` = local merge of the 10 launcher-only apps onto the fork's hardened branch (tip built on `pinokio-fork/PMOVES.AI-Edition-Hardened f5e5073c1`; 1303 commits of launcher history preserved). Reversible, unpushed — the starting point for step 3.
