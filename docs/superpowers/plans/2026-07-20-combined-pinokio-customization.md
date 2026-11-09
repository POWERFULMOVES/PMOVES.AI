# Combined PMOVES Pinokio Customization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PMOVES-pinokio the single combined home for all PMOVES Pinokio customizations via submodule aggregation (Model A), while each service-owned launcher also lives in its own fork.

**Architecture:** PMOVES-pinokio (fork of the Pinokio app) carries the 10 launcher-only apps in-tree and references `pmoves-crush`, `pmoves-claude-code`, and the `plugin/code` collection as submodules. The meta-repo's `pbnj/` becomes one submodule → PMOVES-pinokio. Claude Code integration lands via the extension surface (a closed CLI, no binary fork).

**Tech Stack:** git submodules, GitHub (`gh`), Pinokio launcher JS (`pinokio.js`/`install.js`/`start.js`), Pinokio's built-in auto-cli `installable` generator.

## Global Constraints

- Each repo change is its own **atomic PR**; fork repos use branch `PMOVES.AI-Edition-Hardened`.
- **Do not depend on Pinokio cloning `--recurse-submodules`.** Every submoduled launcher's `install.js` runs `git submodule update --init --recursive` explicitly.
- **Phase-1 submodule boundary:** only `pmoves-crush` and `pmoves-claude-code` are submoduled; `pmoves-agent-zero` and `pmoves-remote` stay in-tree (their service repos haven't claimed their launchers yet).
- **Disjoint sets:** the 10 in-tree launchers do not include `pmoves-crush`; no collision with Crush's distributed launcher.
- **Never commit secrets.** Launcher env comes from Pinokio env files / runtime, not committed defaults.
- The claude plugin must launch claude-code **pointed at PMOVES-claude-code**, never bare `npx @anthropic-ai/claude-code`.
- The full Claude Code integration *content* (hooks/skills/CHIT/MCP substance) is **out of scope here** — task #13's own spec. This plan builds the structure + a minimal bootstrap.

---

## File Structure

| Repo | Created / Modified | Responsibility |
|------|--------------------|----------------|
| `POWERFULMOVES/code` (new fork of `pinokiocomputer/code`) | Modify `code/claude/pinokio.js` | Code-plugin collection; `claude` repointed at PMOVES-claude-code |
| `POWERFULMOVES/PMOVES-claude-code` | Create `pinokio/api/pmoves-claude-code/{pinokio.js,install.js,start.js}`; `claude-config/` bootstrap | Own launcher + launcher-consumable PMOVES config scaffold |
| `POWERFULMOVES/PMOVES-pinokio` | Add `api/pmoves-*` (10, from verified merge); add submodules `api/pmoves-crush`, `api/pmoves-claude-code`, `plugin/code`; add `install.js` submodule-init | The combined home |
| `POWERFULMOVES/PMOVES.AI` (meta) | `git rm -r pbnj/`; add `pbnj` submodule; fix path refs | References the combined fork |

---

### Task 1: Fork pinokiocomputer/code and repoint the claude plugin

**Files:**
- Fork: `pinokiocomputer/code` → `POWERFULMOVES/code`
- Modify: `claude/pinokio.js` (the claude code-plugin)

**Interfaces:**
- Produces: a `POWERFULMOVES/code` repo on branch `PMOVES.AI-Edition-Hardened` whose `claude` plugin launches claude-code with PMOVES-claude-code config; consumed as the `plugin/code` submodule in Task 3.

- [ ] **Step 1: Fork and branch**

```bash
gh repo fork pinokiocomputer/code --org POWERFULMOVES --fork-name code --clone=false
gh api repos/POWERFULMOVES/code/git/refs --method POST \
  -f ref=refs/heads/PMOVES.AI-Edition-Hardened \
  -f sha="$(gh api repos/POWERFULMOVES/code/git/ref/heads/main --jq .object.sha)"
```
Expected: fork exists; new branch created.

- [ ] **Step 2: Clone the fork branch into a worktree-adjacent dir**

```bash
git clone -b PMOVES.AI-Edition-Hardened https://github.com/POWERFULMOVES/code.git ../pmoves-code-fork
```

- [ ] **Step 3: Repoint the claude plugin** (`../pmoves-code-fork/claude/pinokio.js`)

Change the launch `message` from bare `npx -y @anthropic-ai/claude-code@latest …` to a variant that (a) ensures PMOVES-claude-code is present and (b) launches claude-code with its config. Concretely, set `CLAUDE_CONFIG_DIR` (or `--settings`) to the PMOVES-claude-code checkout path and keep the `npx` invocation:

```js
// claude/pinokio.js — launch step env additions (both win32 and non-win32 branches)
env: {
  CLAUDE_CODE_GIT_BASH_PATH: "{{kernel.path('bin/miniconda/Library/bin/bash.exe')}}",
  CLAUDE_CONFIG_DIR: "{{kernel.path('api/pmoves-claude-code/claude-config')}}"
},
message: "npx -y @anthropic-ai/claude-code@latest {{args.prompt ? JSON.stringify(args.prompt) : ''}}",
```
(Keep the vanilla `npx` binary — the CLI is closed; PMOVES customization is delivered by `CLAUDE_CONFIG_DIR` pointing at the PMOVES-claude-code config scaffold.)

- [ ] **Step 4: Verify the edit is well-formed**

Run: `node -e "require('../pmoves-code-fork/claude/pinokio.js')"`
Expected: no syntax error (module loads).

- [ ] **Step 5: Commit + push + PR**

```bash
git -C ../pmoves-code-fork add claude/pinokio.js
git -C ../pmoves-code-fork commit -m "feat(claude): launch claude-code with PMOVES-claude-code config dir"
git -C ../pmoves-code-fork push origin PMOVES.AI-Edition-Hardened
```

---

### Task 2: PMOVES-claude-code launcher + config scaffold

**Files** (all at PMOVES-claude-code **repo root**, so the submodule at `api/pmoves-claude-code` places `pinokio.js` where Pinokio expects it):
- Create: `pinokio.json`, `install.js`, `start.js` (repo root)
- Create: `claude-config/settings.json` (minimal PMOVES bootstrap — MCP + hooks placeholder)

**Interfaces:**
- Consumes: nothing (leaf).
- Produces: `api/pmoves-claude-code` launcher (submoduled in Task 3) and `claude-config/` (referenced by Task 1's `CLAUDE_CONFIG_DIR`).

- [ ] **Step 1: Scaffold the launcher via the auto-cli installable pattern** (repo root)

Create `pinokio.json`:
```json
{ "title": "PMOVES Claude Code", "description": "Claude Code with full PMOVES context", "icon": "icon.png" }
```

- [ ] **Step 2: install.js** — ensures the repo + its config are present (idempotent)

```js
module.exports = {
  run: [{
    method: "shell.run",
    params: { message: "git submodule update --init --recursive" }
  }]
}
```

- [ ] **Step 3: start.js** — launch claude-code with PMOVES config

```js
module.exports = {
  daemon: true,
  run: [{
    method: "shell.run",
    params: {
      env: { CLAUDE_CONFIG_DIR: "{{cwd}}/claude-config" },
      message: "npx -y @anthropic-ai/claude-code@latest",
      input: true
    }
  }]
}
```

- [ ] **Step 4: Minimal PMOVES bootstrap config** — `claude-config/settings.json`

```json
{ "$comment": "Minimal PMOVES bootstrap. Full hooks/skills/MCP substance is task #13.",
  "env": { "PMOVES_NODE_ID": "z890" } }
```

- [ ] **Step 5: Verify JS loads + JSON valid**

Run: `node -e "require('./start.js'); require('./install.js')" && python -c "import json; json.load(open('claude-config/settings.json'))"`
Expected: no error.

- [ ] **Step 6: Commit + push**

```bash
git add pinokio.json install.js start.js icon.png claude-config
git commit -m "feat(launcher): pmoves-claude-code launcher + minimal PMOVES config scaffold"
git push origin PMOVES.AI-Edition-Hardened
```

---

### Task 3: Assemble the PMOVES-pinokio combined fork

**Files:**
- Base: worktree `D:/PMOVES.AI/pmoves-pbnj-submodule`, branch `pinokio-hardened-merge` (10 launchers already merged onto fork hardened).
- Add submodules: `api/pmoves-crush`, `api/pmoves-claude-code`, `plugin/code`.
- Create: `api/pmoves-crush/install.js` + `api/pmoves-claude-code/install.js` submodule-init shims if not carried.

**Interfaces:**
- Consumes: Task 1 (`POWERFULMOVES/code`), Task 2 (`PMOVES-claude-code`), PMOVES-crush (existing).
- Produces: PMOVES-pinokio hardened branch = the combined home; consumed by Task 4.

- [ ] **Step 1: Add submodules + the crush thin-entry** (in the `pinokio-hardened-merge` branch)

`pmoves-claude-code` and `plugin/code` are shaped with their launcher/plugins at repo root, so they submodule directly at their api/plugin path. `pmoves-crush`'s launcher is nested in its repo (`pbnj/pinokio/api/pmoves-crush/`), so it is pinned under `sources/` and surfaced via a thin in-tree api entry that delegates (respects Crush's structure, keeps version-pinning).

```bash
cd D:/PMOVES.AI/pmoves-pbnj-submodule && git checkout pinokio-hardened-merge
git submodule add -b PMOVES.AI-Edition-Hardened https://github.com/POWERFULMOVES/PMOVES-claude-code.git api/pmoves-claude-code
git submodule add -b PMOVES.AI-Edition-Hardened https://github.com/POWERFULMOVES/code.git plugin/code
git submodule add -b PMOVES.AI-Edition-Hardened https://github.com/POWERFULMOVES/PMOVES-crush.git sources/pmoves-crush
```

Create the thin delegating entry `api/pmoves-crush/pinokio.js` (in-tree) that loads the nested crush launcher from the submodule:
```js
// api/pmoves-crush/pinokio.js — delegate to the crush launcher pinned in sources/
module.exports = require("../../sources/pmoves-crush/pbnj/pinokio/api/pmoves-crush/pinokio.js")
```
And `api/pmoves-crush/install.js` runs `git submodule update --init --recursive` first so `sources/pmoves-crush` is present before the delegate resolves.

Expected: three `.gitmodules` entries (`api/pmoves-claude-code`, `plugin/code`, `sources/pmoves-crush`) + the in-tree `api/pmoves-crush/` thin entry.

- [ ] **Step 2: Add a top-level install shim** so `git submodule update --init --recursive` runs on install (`install.js` at repo root, or per-launcher)

```js
module.exports = { run: [{ method: "shell.run", params: { message: "git submodule update --init --recursive" } }] }
```

- [ ] **Step 3: Verify submodule wiring**

Run: `git submodule status`
Expected: three entries (`api/pmoves-crush`, `api/pmoves-claude-code`, `plugin/code`), each on its hardened branch.

- [ ] **Step 4: Push the combined fork** (this is the first outward-facing irreversible step — checkpoint with operator)

```bash
git push pinokio-fork pinokio-hardened-merge:PMOVES.AI-Edition-Hardened
```
Expected: fork hardened branch now carries app + 10 in-tree launchers + 3 submodules. If protected, push a PR branch instead.

---

### Task 4: Convert meta-repo pbnj/ to a submodule + fix path refs

**Files:**
- Remove: `pbnj/` (80 loose files)
- Modify: `.gitmodules` (add `pbnj`)
- Modify: `deploy/runbooks/pinokio-pbnj-install.md`, `.hermes/plans/2026-07-10_pmoves-p8-launcher-mesh-plan.md` (`pbnj/pinokio/api/*` → `pbnj/api/*`)

**Interfaces:**
- Consumes: Task 3 (PMOVES-pinokio hardened branch).
- Produces: meta-repo referencing the combined fork.

- [ ] **Step 1: Remove loose pbnj + add submodule** (on a fresh branch off `origin/main`)

```bash
git worktree add -b chore/pbnj-meta-submodule ../pmoves-pbnj-meta origin/main
cd ../pmoves-pbnj-meta
git rm -r pbnj
git submodule add -b PMOVES.AI-Edition-Hardened https://github.com/POWERFULMOVES/PMOVES-pinokio.git pbnj
```

- [ ] **Step 2: Fix path references** (`pbnj/pinokio/api/` → `pbnj/api/`)

Edit `deploy/runbooks/pinokio-pbnj-install.md` and `.hermes/plans/2026-07-10_pmoves-p8-launcher-mesh-plan.md`: replace every `pbnj/pinokio/api/` with `pbnj/api/`.

- [ ] **Step 3: Verify relative paths still resolve**

Check each launcher `start.js`/`install.js` under `pbnj/api/*` for `../../pmoves` refs; confirm they resolve against the Pinokio install layout (`D:\pinokio`), not the meta mirror. Note any that break; fix or document.

- [ ] **Step 4: Verify + commit**

Run: `git submodule status --recursive | grep pbnj`
Expected: `pbnj` resolves with nested submodules.

```bash
git add .gitmodules pbnj deploy/runbooks/pinokio-pbnj-install.md .hermes/plans/2026-07-10_pmoves-p8-launcher-mesh-plan.md
git commit -m "chore(pbnj): convert to submodule of PMOVES-pinokio + fix path refs"
```

---

### Task 5: Point the D:\pinokio install at the combined fork + end-to-end validation

**Files:** none in-repo (install-side).

**Interfaces:**
- Consumes: Tasks 1–4.

- [ ] **Step 1: Back up + repoint the install**

Confirm the current `D:\pinokio` app origin; set it to `POWERFULMOVES/PMOVES-pinokio` (branch `PMOVES.AI-Edition-Hardened`), or reinstall Pinokio from the fork. Preserve the operator's existing `env.tier-*` and secrets.

- [ ] **Step 2: Install each launcher from the combined fork**

For each `api/pmoves-*`: run its install (triggers `git submodule update --init --recursive`), confirm no error.

- [ ] **Step 3: Validate the claude plugin routes to PMOVES**

Launch the `claude` code-plugin; confirm `CLAUDE_CONFIG_DIR` points at `api/pmoves-claude-code/claude-config` (PMOVES bootstrap loaded), not vanilla.

- [ ] **Step 4: Validate distributed path intact**

Confirm `pmoves-crush` still installs/runs from its own PMOVES-crush repo unchanged.

- [ ] **Step 5: Full recursive status**

Run: `git -C D:/PMOVES.AI/PMOVES.AI submodule status --recursive`
Expected: `pbnj` and all nested submodules resolve clean.

---

## Notes

- Tasks 1, 2, 4 are safe/reversible until push. **Task 3 Step 4 (push to the fork) is the first irreversible outward-facing step — checkpoint with the operator**, consistent with how this design was gated throughout.
- The verified base artifact for Task 3 is `pinokio-hardened-merge` (10 launchers, 1303 commits history preserved) in worktree `D:/PMOVES.AI/pmoves-pbnj-submodule`.
- Deferred: PMOVES-claude-code deep-integration content (task #13 spec); auto-cli generator can regenerate any launcher whose `start.js` needs to change.
