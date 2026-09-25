# P7 Playground — Pinokio-Launched VS Code + PMOVES Harness Plugins: Implementation Plan and Runbook

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Pinokio launcher work additionally REQUIRES the `gepeto` skill (`~/.claude/skills/gepeto/SKILL.md`, its six-step Non-Negotiable Execution Workflow) and the `pinokio` skill (pterm-first runtime control). Room work uses the `p7-stage` skill. Recall from and store to Cipher (`pmoves-cipher-local`, agentId = your signing-card id) before and after each phase.

**Goal:** Agent sessions on a PMOVES node run under Pinokio, not inside an editor, and use PMOVES-customized harness plugins and a PMOVES-customized VS Code. Every installed plugin must be reproducible from a tracked git ref.

**Architecture:** Pinokio owns the interactive agent sessions through PMOVES harness plugins bundled in PMOVES-registry (installed into Pinokio as an app, with PMOVES metadata in sidecar files and everything rendered from `pmoves/configs/cli_tools.yaml` + `pmoves/config/agent_registry.yaml`), while Spynel drives the same harnesses over ACP from the same registry.

**Tech Stack:** Pinokio 8.2.0 (plugin schema per `PINOKIO.md` "Building a plugin"), pterm 0.0.25, Python 3 stdlib + unittest, GNU make, bash; VS Code portable build; the ACP registry (PMOVES-registry fork).

**Spec:** `pmoves/docs/services/IDE_PINOKIO_FLEET_CONSOLE_PLAN.md` (§3 "Pinokio mirror", §Sequencing) and `pmoves/docs/archive/AGNOTE_P7_PLAYGROUND-2026-04-10.md` (Step 5 "Pinokio as Agent Runtime Layer", lines 226-246; "Remaining P7 Items" item 3, line 376).

## Provenance Ledger (measured 2026-09-24 on Knuckles, B850; re-measure before relying on any row)

| # | Fact | Source / how measured |
|---|------|------------------------|
| P1 | The goal is P7 "Pinokio as Agent Runtime Layer", which covers isolation, discovery, customization, resumption and remote control ("Why P7 > Raw IDE") | `pmoves/docs/archive/AGNOTE_P7_PLAYGROUND-2026-04-10.md:226-246` |
| P2 | "Route P7 launcher through room/stage selection" is P0 and still open | same file `:376` |
| P3 | The fleet-console plan is PROPOSAL. Its Sequencing step 1 (.vscode) is not done: there is no `.vscode/mcp.json`, and `mcp_config_generator.py` has no `vscode` renderer | `IDE_PINOKIO_FLEET_CONSOLE_PLAN.md:3,90-95`; `ls .vscode/mcp.json`; `grep -c vscode pmoves/tools/mcp_config_generator.py` → 0 |
| P4 | Sequencing step 4 is in flight as PMOVES-pinokio PR #12 (`api/pmoves-fleet`, `api/pmoves-hermes`), OPEN/BLOCKED, last updated 2026-09-06. PR #11 (sync of the hardened branch to Pinokio 8.2.0) is also OPEN/BLOCKED | `gh pr view 11,12 -R POWERFULMOVES/PMOVES-pinokio` |
| P5 | `fleet_sentinel` (plan §4) exists as code but is not running | `ls pmoves/services/fleet_sentinel`; `docker ps` has no sentinel |
| P6 | Installed Pinokio is the upstream 8.2.0 .deb (`/opt/Pinokio`), not a PMOVES-pinokio fork build | `dpkg -l pinokio` → 8.2.0 |
| P7 | Installed `PINOKIO_HOME/plugin/code` is upstream `pinokiocomputer/code`, not the POWERFULMOVES/code fork | `git -C ~/pinokio/plugin/code remote -v` |
| P8 | The POWERFULMOVES/code fork (`PMOVES.AI-Edition-Hardened`) is 2 commits ahead of upstream: `claude/pinokio.js` sets `CLAUDE_CONFIG_DIR` to `api/pmoves-claude-code/claude-config`, and it adds `pmoves-codex/` | `gh api repos/POWERFULMOVES/code/compare/pinokiocomputer:main...POWERFULMOVES:PMOVES.AI-Edition-Hardened` |
| P9 | `pmoves-codex` runs upstream `@openai/codex@latest` with PMOVES env only, so it gets no node identity or Cipher binding. It also defaults `PMOVES_NATS_URL` to a URL with embedded credentials | fork `pmoves-codex/pinokio.js:23,43` |
| P10 | The installed `~/pinokio/plugin/pmoves-crush` is not a git checkout, and its files match neither tracked copy (installed pinokio.js `69276f264537…`, start.js `ad038cdba55e…`; PMOVES-crush `pbnj/pinokio/api/pmoves-crush` @ `d82c07e2`: pinokio.js `d25776482a05…`, start.js `169b3ff767c2…`) | `sha256sum`; `gh api repos/POWERFULMOVES/PMOVES-crush/contents/...` |
| P11 | No Pinokio plugin or launcher script has ever run on this node | `ls ~/pinokio/logs/api ~/pinokio/logs/dev` → absent |
| P12 | Current editor failure mode: the kernel OOM killer killed code-insiders processes 16 times across two boots between 2026-09-22 00:03 and 2026-09-24 14:31 (15 in boot -1, 1 in boot 0). The same window also saw kills of the deb code (1), chrome (5), docker (1) and docker-buildx (1), so container builds are exposed too. 9 VS Code session logs in that window end with "crashed with code 15 and reason 'killed'". Agents are children of the editor (claude ← bash ← code-insiders(ptyHost) ← code-insiders), so each session loss ended every agent lane. | per boot, because journalctl -k reads only the current boot: `for b in -1 0; do journalctl -b $b -k --since 2026-09-22 \| grep -oE 'Killed process [0-9]+ \([a-z-]+\)'; done`; session logs: `grep -l "reason 'killed'" ~/.config/Code\ -\ Insiders/logs/2026092[2-4]*/main.log`; process ancestry |
| P13 | Snap update hold works (`code-insiders` held at rev 2558 while 2560 is pending), so updates are not the crash cause | `snap list`; `snap refresh --list` |
| P14 | Plugin schema: `path: "plugin"` is required for standalone plugins. `launch_type` is inferred (`shell.run` → terminal, `exec`/`app.launch` → desktop). `run` is required. `install`/`uninstall`/`update`/`installed` are optional | `~/pinokio/prototype/PINOKIO.md:2855-2875` |
| P15 | `PINOKIO.md` is byte-identical to the live https://desktop.pinokio.co/docs/ (Last-Modified 2026-09-05), which is built from `pinokiocomputer/home` `docs/README.md` @ `2d8d87d9e` (2026-09-02). The fork `POWERFULMOVES/Pmoves-program.pinokio.computer` is stale (upstream last commit 2025-06-06, no plugin chapter) | `cmp`; `gh api` commit queries |
| P16 | Reference example for plugins: `~/pinokio/prototype/system/examples/plugin_installable_agent/` pins `version: "7.0"` (SPEC.md "Keep version 7.0"), while PINOKIO.md 8.2 examples show `version: "8.0.0"`. Treat this as a known docs contradiction and follow the example (gepeto Example Lock-in) | `pinokio.js:2`; `SPEC.md` Structure Rules; `PINOKIO.md` Instant/Installable Plugins |
| P17 | Harness source of truth: `pmoves/configs/cli_tools.yaml` + `pmoves/config/agent_registry.yaml`, rendered by `pmoves/tools/pmoves_launcher_generator.py` (#3092, #3149) into `deploy/provision/*-pmoves.{sh,ps1,cmd}` | generator module docstring; Scout C inventory |
| P18 | PMOVES-registry is a fork of the upstream ACP registry: 42 upstream entries, and only `kilo → kilocode_glm` is linked (`pmoves/configs/acp_registry_map.json`). The `spynel` explicit bridge is dead. `TAC_ACP_REGISTRY.md` was deleted from HEAD (last present at `95c6934c7`) | `pmoves/tools/acp_registry_map.py:33-39`; `git show 95c6934c7:pmoves/docs/TAC/TAC_ACP_REGISTRY.md` |
| P19 | Spynel's workspace config (`.spynel/config.yaml`) has `harness.*`, `channels.*` and `speech.*` keys and no ACP or registry key. `~/pmoves-node/spynel-workspace` (its `--config` path) is missing or empty on Knuckles | key-only dump (values masked) |
| P20 | P7 room orchestrator is running (`pmoves-p7`, :8120, `rooms_loaded:15`). `p7.nats.launch` / `p7.nats.session` are "reserved" with no confirmed production publisher | `curl :8120/healthz`; `pmoves/docs/ROOMS_ON_A_STAGE.md:112` |
| P21 | Pinokio 8.2 loads 15 plugins: 14 built-in (antigravity-cli[-auto], claude[-auto], claude-desktop, codex[-auto], codex-desktop, cursor, grok[-auto], opencode[-auto], vscode) plus 1 app-bundled (hermes-agent → no-gateway). `plugin/code/*` and `plugin/pmoves-crush` are NOT loaded: 8.2 needs one pinokio.js per plugin folder with a `run` array; `plugin/code` is a nested collection, and pmoves-crush has `menu` but no `run` | Pinokio `/plugins` page with the app started via `systemd-run --user`; `PINOKIO.md:2867,8675-8682` |
| P22 | The built-in Claude plugins run upstream `npx @anthropic-ai/claude-code@latest` with no PMOVES identity, Cipher or damage-control. `claude-auto` adds `--dangerously-skip-permissions` | `/opt/Pinokio/resources/app.asar.unpacked/node_modules/pinokiod/system/plugin/claude-auto/pinokio.js` |
| P23 | App-bundled plugins: an app launcher's top-level `plugins: ["plugins/x/pinokio.js"]`, resolved relative to the launcher root (a launcher at `/api/app/pinokio/pinokio.js` has root `/api/app/pinokio`). Live reference: hermes-agent.pinokio, whose `plugins/no-gateway` resolves paths with `{{path.resolve(dirname, ...)}}` | `PINOKIO.md:2246-2251,3112-3140`; `~/pinokio/api/hermes-agent.pinokio.git/pinokio.js:9-11` |
| P24 | PMOVES-registry `main` is still pure upstream: 42 entries (distribution: npx 23, binary 19, uvx 2), no PMOVES or Crush entry. Entries describe ACP SERVERS (JSON-RPC over stdio), not interactive TUIs; e.g. claude-acp is `@agentclientprotocol/claude-agent-acp`. Schema properties: authors, description, distribution, icon, id, license, license_url, name, preview, repository, version, website; `additionalProperties` unset | local checkout `~/pmoves-node/PMOVES-registry` (`FORMAT.md`, `agent.schema.json`, `*/agent.json`) |
| P25 | Pinokio 8.2 has no ACP or agent-registry support | grep of PINOKIO.md and pinokiod for agentclientprotocol/ACP: no functional hits |
| P26 | Spynel (the ACP client/cockpit) has a compiled-in harness catalog: native codex, claude-code, pi; `agent-zero` via `a0 acp`; ACP aliases opencode, qwen-code, kimi, goose, cursor, gemini-cli, github-copilot, factory-droid; plus one custom `acp` slot (`harness.acp_command`/`acp_args`). It has no registry loader | `~/pmoves-node/PMOVES-spynel/internal/harness/catalog.go:34-61`; `docs/configuration.md:72,82-83,100-105` |
| P27 | ACP capability on Knuckles: `kimi acp` ✓, `kilo acp` ✓, `crush acp` ✗ (v0.92.0 errors; PMOVES-crush `internal/backend/backend.go:3` names ACP only as a planned layer), `a0` not installed. Agent Zero 2.13 ships ACP as the bundled plugin `plugins/_a0_acp` (connector: `a0 acp --host <url>`) | local CLI probes; `PMOVES-Agent-Zero/plugins/_a0_acp/README.md` |
| P28 | Pinokio 8.2's Caddy grew to 4.3G RSS in 9h because Pinokio reloaded its config ~23 times a minute (184 `/load` admin requests in 8 min, each restarting the HTTP server). Pinokio was stopped to recover memory | `~/pinokio/logs/caddy.log`; `ps` |
| P29 | About 25 git worktrees at `~/pinokio/api/pmoves-*` are registered as Pinokio apps and pollute `pterm search` | `pterm search pmoves` |

## Global Constraints

- Plugin shape mirrors `~/pinokio/prototype/system/examples/plugin_installable_agent/pinokio.js`: metadata in the root `pinokio.js`, no separate `pinokio.json`, no `install.js`/`start.js`/`reset.js`/`update.js`, and `run` targets `{{args.cwd}}` (SPEC.md Structure Rules).
- Never edit upstream checkouts. PMOVES harness plugins go to `POWERFULMOVES/PMOVES-registry` (D2), with PMOVES metadata in sidecars so upstream entry dirs stay byte-identical (D5). App changes go to `POWERFULMOVES/PMOVES-pinokio`.
- Every plugin installed on a node must resolve to a tracked git ref. A hand-copied plugin is a finding (see P10).
- No absolute paths or hardcoded binaries in scripts: use `{{which('x')}}`, `{{kernel.path(...)}}`, `{{args.cwd}}` (gepeto "shell.run API").
- No credentials in committed files. `nats://nats:pmoves@…` defaults (P9, and `.vscode/settings.json` `terminal.integrated.env.*`) become `{{envs.PMOVES_NATS_URL}}` with no credentialed default.
- Tool exit codes: 0 clean / 1 findings / 3 could-not-measure. Always print the input counts beside a result.
- Harness customization is read from the P17 source of truth. Do not create a second registry.
- Live services are not touched by this plan's delivery tasks. Phase 0 runtime checks are runbook steps run by the operator or steward.

## Review Focus

1. **Pinokio itself dies:** moving sessions from the editor to Pinokio makes Pinokio the new single point of failure. The expected behaviour is that agent sessions survive an editor crash, and that a Pinokio crash is documented, not silent. Pinned by Task 0.2 step 5.
2. **Windows node:** plugins must pick bash through `shell: "{{kernel.path('bin/miniforge/Library/bin/bash.exe')}}"` (the 8.2 built-in pattern, P22), and wrappers must have a `.ps1` path. Pinned by Task 2.1 step 1 (the win32 branch is required by the test).
3. **Wrapper missing or repo elsewhere:** the plugin must fail visibly in its menu (the `pmoves-crush` pattern, installed `pinokio.js:37-43`), not error in a shell. Pinned by Task 2.1 step 1.
4. **Two sources for one plugin** (a loose `plugin/pmoves-crush` or `plugin/code` next to the registry-bundled plugin): the provenance tool must flag the loose copy. Pinned by Task 1.1 test `test_loose_plugin_is_untracked`.
5. **Memory:** a portable VS Code per room multiplies Electron memory. On Linux each room runs under `systemd-run --user --scope -p MemoryMax=`, and the Windows gap is documented. Pinned by Task 2.3. Pinokio's own Caddy is a second unbounded consumer (P28), pinned by Task 0.3. The OOM killer has also killed docker and docker-buildx on this node (P12), so image builds must not run while an editor's memory is unbounded.

## Operator Decisions (gates; each task below names the decision it depends on)

- **D1 (open): IDE set.** VS Code is present (deb Stable 1.138 = what Pinokio's built-in vscode plugin opens via which('code'); snap Insiders = the OOM-killed one). The Antigravity IDE is downloaded (~/Downloads/Antigravity.tar.gz) but not installed; the Antigravity CLI (agy) is installed and covered by the built-in antigravity-cli plugin. Cursor has a built-in plugin but is not installed. Open question: which IDEs get PMOVES desktop plugins, and installed or portable-pinned builds.
- **D2 (decided 2026-09-25):** plugins are bundled in PMOVES-registry (the harness target for all AGInTZ), declared by a launcher at PMOVES-registry/pinokio/pinokio.js. The earlier proposal of subfolders in the POWERFULMOVES/code fork is RETRACTED: Pinokio 8.2 does not load nested collections (P21).
- **D3: Docs pin.** Default: fork `pinokiocomputer/home` as `POWERFULMOVES/PMOVES-pinokio-home`, so the docs source (P15) is pinned. `Pmoves-program.pinokio.computer` is left stale.
- **D4: Pinokio build.** Default: keep the upstream 8.2.0 .deb (P6) through Phase 2, and switch to the PMOVES-pinokio build after PR #11 merges.
- **D5 (decided 2026-09-25):** PMOVES metadata lives in sidecar files at PMOVES-registry/pmoves/sidecars/<id>.json, never inside upstream entry dirs, so weekly upstream syncs stay conflict-free.

## File Structure

| Path | Repo | Responsibility | Phase |
|------|------|----------------|-------|
| `pmoves/tools/pinokio_plugin_provenance.py` | PMOVES.AI | Classify each installed plugin as fork / upstream / dirty / untracked / unmeasured | 1 |
| `pmoves/tools/tests/test_pinokio_plugin_provenance.py` | PMOVES.AI | unittest suite for the above | 1 |
| `pmoves/mk/pinokio.mk` + `include mk/pinokio.mk` in `pmoves/Makefile` | PMOVES.AI | `pinokio-plugin-provenance`, `pinokio-plugins-install` targets | 1 |
| `pinokio/pinokio.js` | PMOVES-registry | App launcher "PMOVES Registry": top-level `plugins` array + menu listing the bundled plugins (P23) | 2 |
| `pinokio/plugins/pmoves-*/pinokio.js` | PMOVES-registry | One terminal plugin per PMOVES harness wrapper; `pmoves-crush` replaces the loose `plugin/pmoves-crush` (P10) | 2 |
| `pinokio/test/*.test.js` | PMOVES-registry | node:test suite for the launcher and plugins | 2 |
| `pmoves/sidecars/*.json` | PMOVES-registry | PMOVES metadata per harness, outside upstream entry dirs (D5) | 2 |
| `pmoves/sidecar.schema.json` | PMOVES-registry | JSON Schema for the sidecars | 2 |
| `pmoves/tools/pmoves_launcher_generator.py` (renderers `registry_sidecar`, `registry_plugin`) | PMOVES.AI | Emit sidecars and registry-bundled plugins from cli_tools.yaml + agent_registry.yaml | 3 |
| PMOVES-registry `pmoves-*/agent.json` | PMOVES-registry | ACP entries for PMOVES harnesses that have an ACP server | 4 |
| PMOVES-spynel registry + sidecar loader | PMOVES-spynel | Harness catalog from PMOVES-registry instead of the compiled-in list (P26) | 4 |
| room manifest `plugins:` overlay + `p7` publisher | PMOVES.AI | Room → plugin set; `p7.nats.launch/session` | 5 |

Phases 3-5 are outlines. Each gets its own detailed plan once the gate before it passes, because their design depends on what Phase 0 measures (YAGNI).

---

## Phase 0: Runbook — stop the damage and test the premise (operator + steward; no code)

### Task 0.1: Take agents out of the editor's process tree

- [ ] **Step 1: Free memory now.** Close the deb `code` window (1.138, about 2.2 GB RSS at measurement time; see P12). Verify:
```bash
ps -C code -o rss= | awk '{s+=$1}END{printf "deb code RSS: %.1fG\n",s/1048576}'   # expect 0.0G
free -m | sed -n 2,3p
```
- [ ] **Step 2: Start the next agent sessions in tmux, not in a VS Code terminal.**
```bash
tmux new-session -d -s steward -c "$HOME/pinokio/api/PMOVES.AI" 'pmoves/scripts/claude-pmoves.sh'
tmux attach -t steward          # attach from any terminal, including VS Code's
```
- [ ] **Step 3: Prove the session is no longer the editor's child.** Expected: no `code-insiders` in the chain.
```bash
p=$(pgrep -n -f 'claude' ); while [ "$p" -gt 1 ]; do ps -o comm=,pid= -p "$p"; p=$(ps -o ppid= -p "$p" | tr -d ' '); done
```

### Task 0.2: Survival spike — does a Pinokio plugin session outlive the editor? (Gate G0)

- [ ] **Step 1: Start Pinokio** (the installed 8.2.0 .deb, P6) from the desktop menu (`/usr/share/applications/pinokio.desktop`), then verify:
```bash
curl -s -m3 http://127.0.0.1:42000/pinokio/home     # expect JSON with "path": "/home/<user>/pinokio"
```
- [ ] **Step 2: Launch a plugin session headlessly** (pterm syntax: `PTERM.md` §start, lines 107-140):
```bash
PT="$HOME/pinokio/bin/npm/bin/pterm"
"$PT" start "$HOME/pinokio/plugin/pmoves-crush/start.js" -- --cwd="$HOME/pinokio/api/PMOVES.AI"
```
- [ ] **Step 3: Record the ancestry.** Expected: the chain reaches the Pinokio process (`/opt/Pinokio/...`) and contains no `code-insiders`.
```bash
p=$(pgrep -n -f 'charmland/crush'); while [ "$p" -gt 1 ]; do ps -o comm=,pid=,args= -p "$p" | cut -c1-120; p=$(ps -o ppid= -p "$p" | tr -d ' '); done
```
- [ ] **Step 4: Editor-kill confirmation (only from a tmux session, never from a VS Code terminal).** Close all VS Code windows, then re-run Step 3. Expected: the same PID is still alive.
- [ ] **Step 5: Pinokio-kill observation (Review Focus 1).** `pkill -f /opt/Pinokio`, then re-run Step 3. Record whether the session died. The expected outcome is that it dies. Record it either way, because it sets the Phase 2 requirement for relaunch and resumption.
- [ ] **Step 6: Record the evidence.** Run `make -C pmoves register-note` with the three ancestry captures, and store the result in Cipher (category `decision`, tags `p7-playground`, `pinokio`, `process-model`).

**Gate G0:** if Step 4's session dies with the editor, STOP. The premise is false and the plan must be revised before Phase 1.

### Task 0.3: Diagnose the Caddy reload loop (P28) before relying on Pinokio

- [ ] **Step 1: Start Pinokio outside any editor's process tree**, as a transient user unit, then verify it answers:
```bash
systemd-run --user --unit=pinokio-app --collect /opt/Pinokio/pinokio
curl -s -m3 http://127.0.0.1:42000/pinokio/home     # expect JSON with "path"
```
- [ ] **Step 2: Count config reloads over 60 seconds.** Print both counts beside the rate.
```bash
L="$HOME/pinokio/logs/caddy.log"
a=$(grep -c '"uri":"/load"' "$L"); sleep 60; b=$(grep -c '"uri":"/load"' "$L")
echo "caddy /load requests in 60s: $((b-a)) (before=$a after=$b)"   # P28 measured ~23/min
```
- [ ] **Step 3: Watch Caddy's RSS** for five minutes:
```bash
for i in 1 2 3 4 5; do ps -C caddy -o pid=,rss= | awk '{printf "caddy pid %s RSS %.2fG\n",$1,$2/1048576}'; sleep 60; done
```
- [ ] **Step 4: Test the worktree hypothesis (P29).** Stop Pinokio (`systemctl --user stop pinokio-app`), run Task 0.4, then repeat Steps 1-3. Record the reload rate and RSS slope before and after. If the rate does not change, the worktrees are not the cause, and that result is recorded too.
- [ ] **Step 5: Record the result.** Run `make -C pmoves register-note` with both reload counts, the RSS samples, and the before/after comparison, and store it in Cipher (category `diagnosis`, tags `p7-playground`, `pinokio`, `caddy`). If the rate stays high, stop Pinokio with `systemctl --user stop pinokio-app`.

**Gate:** do not run long agent sessions under Pinokio until the reload rate is understood.

### Task 0.4: Move agent worktrees out of `PINOKIO_HOME/api` (P29)

- [ ] **Step 1: List the worktrees Pinokio sees as apps.**
```bash
R="$HOME/pinokio/api/PMOVES.AI"
git -C "$R" worktree list --porcelain | awk '/^worktree /{print $2}' | grep "^$HOME/pinokio/api/pmoves-" | tee /tmp/p29-worktrees.txt | wc -l
```
- [ ] **Step 2: Classify each one as merged/unmerged and clean/dirty.**
```bash
git -C "$R" fetch -q origin main
while read -r w; do
  dirty=$(git -C "$w" status --porcelain | wc -l)
  if git -C "$R" merge-base --is-ancestor "$(git -C "$w" rev-parse HEAD)" origin/main; then merged=yes; else merged=no; fi
  echo "$w dirty=$dirty merged=$merged"
done < /tmp/p29-worktrees.txt | tee /tmp/p29-classified.txt
```
A squash-merged branch is not an ancestor of `origin/main`, so it classifies as `merged=no` and is moved rather than removed. That is the safe direction.
- [ ] **Step 3: Remove merged and clean worktrees; move all others.**
```bash
mkdir -p "$HOME/pmoves-worktrees"
awk '$2=="dirty=0" && $3=="merged=yes"{print $1}' /tmp/p29-classified.txt | while read -r w; do git -C "$R" worktree remove "$w"; done
awk '!($2=="dirty=0" && $3=="merged=yes"){print $1}' /tmp/p29-classified.txt | while read -r w; do git -C "$R" worktree move "$w" "$HOME/pmoves-worktrees/$(basename "$w")"; done
```
Never delete an unmerged or dirty worktree, and never add `--force`. If git refuses because a worktree has populated submodules ("working trees containing submodules cannot be moved or removed"), leave it in place, list it in the Task 0.3 register NOTE, and ask its owner.
- [ ] **Step 4: Verify.** `git -C "$R" worktree list | grep -c "$HOME/pinokio/api/pmoves-"` prints the count of refused worktrees from Step 3 (0 if none), and `pterm search pmoves` no longer lists the moved ones.

---

## Phase 1: Provenance before building

### Task 1.1: `pinokio-plugin-provenance` tool (PMOVES.AI)

**Files:**
- Create: `pmoves/tools/pinokio_plugin_provenance.py`
- Create: `pmoves/tools/tests/test_pinokio_plugin_provenance.py`
- Create: `pmoves/mk/pinokio.mk`; Modify: `pmoves/Makefile` (add `include mk/pinokio.mk` after `include mk/build-gate.mk`, line ~238)

**Interfaces:**
- Produces: `resolve_pinokio_home(env: dict[str,str], config_path: Path) -> Path | None`; `classify(plugin_dir: Path) -> PluginReport`; `PluginReport(name, status, remote, head, detail)`, where status ∈ {`fork`,`upstream`,`dirty`,`untracked`,`unmeasured`}; `main(argv) -> int` returning 0/1/3.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for pinokio_plugin_provenance: where does each installed plugin come from?"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TOOLS))

import pinokio_plugin_provenance as ppp  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _make_checkout(path: Path, remote: str) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    _git(path, "remote", "add", "origin", remote)
    (path / "pinokio.js").write_text("module.exports = {}\n")
    _git(path, "add", ".")
    _git(path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    return path


class ResolveHomeTest(unittest.TestCase):
    def test_env_wins(self):
        self.assertEqual(ppp.resolve_pinokio_home({"PINOKIO_HOME": "/x"}, Path("/nope")), Path("/x"))

    def test_config_home(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "config.json"
            cfg.write_text(json.dumps({"home": "/y"}))
            self.assertEqual(ppp.resolve_pinokio_home({}, cfg), Path("/y"))

    def test_unresolvable_is_none(self):
        self.assertIsNone(ppp.resolve_pinokio_home({}, Path("/definitely/missing.json")))


class ClassifyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_fork_checkout(self):
        p = _make_checkout(self.root / "code", "https://github.com/POWERFULMOVES/code.git")
        self.assertEqual(ppp.classify(p).status, "fork")

    def test_upstream_checkout(self):
        p = _make_checkout(self.root / "code", "https://github.com/pinokiocomputer/code")
        self.assertEqual(ppp.classify(p).status, "upstream")

    def test_ssh_fork_remote(self):
        p = _make_checkout(self.root / "code", "git@github.com:POWERFULMOVES/code.git")
        self.assertEqual(ppp.classify(p).status, "fork")

    def test_dirty_checkout(self):
        p = _make_checkout(self.root / "code", "https://github.com/POWERFULMOVES/code.git")
        (p / "pinokio.js").write_text("changed\n")
        self.assertEqual(ppp.classify(p).status, "dirty")

    def test_loose_plugin_is_untracked(self):
        p = self.root / "pmoves-crush"
        p.mkdir()
        (p / "pinokio.js").write_text("module.exports = {}\n")
        self.assertEqual(ppp.classify(p).status, "untracked")

    def test_plugin_nested_in_foreign_repo_is_untracked(self):
        outer = _make_checkout(self.root / "home", "https://github.com/POWERFULMOVES/x.git")
        inner = outer / "plugin" / "loose"
        inner.mkdir(parents=True)
        self.assertEqual(ppp.classify(inner).status, "untracked")


class MainTest(unittest.TestCase):
    def _run(self, home: Path | None) -> int:
        env = {"PINOKIO_HOME": str(home)} if home else {}
        return ppp.main([], env=env, config_path=Path("/definitely/missing.json"))

    def test_unresolvable_home_is_3(self):
        self.assertEqual(self._run(None), 3)

    def test_all_fork_is_0(self):
        with tempfile.TemporaryDirectory() as d:
            _make_checkout(Path(d) / "plugin" / "code", "https://github.com/POWERFULMOVES/code.git")
            self.assertEqual(self._run(Path(d)), 0)

    def test_any_untracked_is_1(self):
        with tempfile.TemporaryDirectory() as d:
            _make_checkout(Path(d) / "plugin" / "code", "https://github.com/POWERFULMOVES/code.git")
            (Path(d) / "plugin" / "pmoves-crush").mkdir()
            self.assertEqual(self._run(Path(d)), 1)

    def test_empty_plugin_dir_is_0_and_reports_zero_seen(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "plugin").mkdir()
            self.assertEqual(self._run(Path(d)), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**
Run: `cd pmoves && python3 -m unittest tools/tests/test_pinokio_plugin_provenance.py -v`
Expected: ERROR `ModuleNotFoundError: No module named 'pinokio_plugin_provenance'`

- [ ] **Step 3: Minimal implementation**

```python
#!/usr/bin/env python3
"""Report where each installed Pinokio plugin comes from.

A plugin under PINOKIO_HOME/plugin with no git checkout of its own is
node-local state: a fresh node cannot reproduce it (plan P10). Exit codes:
0 clean (every plugin is a clean PMOVES fork checkout), 1 findings,
3 could not measure.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

EXIT_CLEAN, EXIT_FINDINGS, EXIT_UNMEASURED = 0, 1, 3
FORK_OWNER = "POWERFULMOVES"


@dataclass
class PluginReport:
    name: str
    status: str  # fork | upstream | dirty | untracked | unmeasured
    remote: str | None
    head: str | None
    detail: str


def resolve_pinokio_home(env: dict[str, str], config_path: Path) -> Path | None:
    if env.get("PINOKIO_HOME"):
        return Path(env["PINOKIO_HOME"])
    try:
        home = json.loads(config_path.read_text()).get("home")
    except (OSError, ValueError):
        return None
    return Path(home) if home else None


def _git(repo: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    except OSError:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def classify(plugin_dir: Path) -> PluginReport:
    name = plugin_dir.name
    top = _git(plugin_dir, "rev-parse", "--show-toplevel")
    if top is None or Path(top).resolve() != plugin_dir.resolve():
        return PluginReport(name, "untracked", None, None, "not its own git checkout: node-local state")
    remote = _git(plugin_dir, "remote", "get-url", "origin")
    head = _git(plugin_dir, "rev-parse", "HEAD")
    status = _git(plugin_dir, "status", "--porcelain")
    if status is None:
        return PluginReport(name, "unmeasured", remote, head, "git status failed")
    if status:
        return PluginReport(name, "dirty", remote, head, "uncommitted changes: installed copy differs from its source")
    if remote and f"/{FORK_OWNER}/" in remote.replace(":", "/"):
        return PluginReport(name, "fork", remote, head, "tracked PMOVES fork")
    return PluginReport(name, "upstream", remote, head, "upstream source: no PMOVES customization")


def main(argv: list[str] | None = None, env: dict[str, str] | None = None,
         config_path: Path | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    env = dict(os.environ) if env is None else env
    config_path = config_path or Path.home() / ".pinokio" / "config.json"
    home = resolve_pinokio_home(env, config_path)
    if home is None or not (home / "plugin").is_dir():
        print(f"pinokio-plugin-provenance: could not resolve PINOKIO_HOME/plugin (got {home})", file=sys.stderr)
        return EXIT_UNMEASURED
    dirs = sorted(p for p in (home / "plugin").iterdir() if p.is_dir())
    reports = [classify(p) for p in dirs]
    if args.json:
        print(json.dumps({"pinokio_home": str(home), "plugins_seen": len(dirs),
                          "reports": [asdict(r) for r in reports]}, indent=2))
    else:
        print(f"PINOKIO_HOME={home} plugins_seen={len(dirs)}")
        for r in reports:
            print(f"  {r.status:<10} {r.name:<24} {r.remote or '-'}  {r.detail}")
    if any(r.status == "unmeasured" for r in reports):
        return EXIT_UNMEASURED
    return EXIT_CLEAN if all(r.status == "fork" for r in reports) else EXIT_FINDINGS


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**
Run: `cd pmoves && python3 -m unittest tools/tests/test_pinokio_plugin_provenance.py -v`
Expected: all 13 tests OK

- [ ] **Step 5: Add make targets** in `pmoves/mk/pinokio.mk`:
```make
# Pinokio plugin provenance + install. Plan: docs/superpowers/plans/2026-09-24-p7-playground-pinokio-plugins.md
# make collapses nonzero exits to 2; call the tool directly when you need 0/1/3.
PINOKIO_CODE_FORK ?= https://github.com/POWERFULMOVES/code.git
PINOKIO_CODE_BRANCH ?= PMOVES.AI-Edition-Hardened

.PHONY: pinokio-plugin-provenance
pinokio-plugin-provenance: ## Classify every installed Pinokio plugin (fork/upstream/dirty/untracked); 0 clean, 1 findings, 3 unmeasured
	@$(PYTHON) tools/pinokio_plugin_provenance.py $(ARGS)
```
Then add `include mk/pinokio.mk` to `pmoves/Makefile`, directly after `include mk/build-gate.mk`.

- [ ] **Step 6: Run it on Knuckles.** Expected output lists `upstream code` (P7) and `untracked pmoves-crush` (P10):
```bash
python3 pmoves/tools/pinokio_plugin_provenance.py; echo "rc=$?"   # expect rc=1
```

- [ ] **Step 7: Commit**
```bash
git add pmoves/tools/pinokio_plugin_provenance.py pmoves/tools/tests/test_pinokio_plugin_provenance.py pmoves/mk/pinokio.mk pmoves/Makefile
git commit -m "feat(pinokio): plugin provenance check — a hand-copied plugin is node-local state"
```

### Task 1.2: Reconcile the loose `pmoves-crush` (P10) — steward-led, no guessing

- [ ] **Step 1: Diff the installed copy against the tracked copy.**
```bash
git -C "$HOME/pinokio/api/PMOVES.AI" show "$(git -C "$HOME/pinokio/api/PMOVES.AI/PMOVES-crush" rev-parse HEAD 2>/dev/null || echo d82c07e2):pbnj/pinokio/api/pmoves-crush/start.js" > /tmp/tracked-start.js 2>/dev/null || gh api "repos/POWERFULMOVES/PMOVES-crush/contents/pbnj/pinokio/api/pmoves-crush/start.js?ref=d82c07e2" --jq .content | base64 -d > /tmp/tracked-start.js
diff -u /tmp/tracked-start.js "$HOME/pinokio/plugin/pmoves-crush/start.js"
```
- [ ] **Step 2: Decide which copy is canonical.** The canonical crush plugin lands as `PMOVES-registry/pinokio/plugins/pmoves-crush/pinokio.js` (Task 2.2). Each hunk the installed copy adds must be carried into that file or dropped with a stated reason in the PR body. One hunk is dropped already: the installed `menu` calls `kernel.path.resolve(...)`, but `kernel.path` is a function (`pinokiod/kernel/index.js:550-552`, extracted from `/opt/Pinokio/resources/app.asar`), so that call throws. Nothing is deleted from the node until the registry plugin is installed and shows on Pinokio's `/plugins` page (P21 method).

---

## Phase 2: PMOVES harness plugins bundled in PMOVES-registry (depends on G0, D2, D5)

Work in a clone of `POWERFULMOVES/PMOVES-registry` on branch `feat/pinokio-harness-plugins` off `main`. Follow gepeto's six steps. Example lock-in: `~/pinokio/prototype/system/examples/plugin_installable_agent/pinokio.js` for plugin shape, and `~/pinokio/api/hermes-agent.pinokio.git/pinokio.js:9-11` + `plugins/no-gateway/pinokio.js` for the app-bundled layout (P23). The new top-level `pinokio/` and `pmoves/` directories hold no `agent.json`, so the registry build skips them (`.github/workflows/build_registry.py:664-672` prints "has no agent.json, skipping"; `verify_agents.py:961-967` skips silently). Upstream entry dirs are never edited (D5).

### Task 2.1: Registry launcher + one plugin (`pmoves-claude`)

**Files (PMOVES-registry):** Create `pinokio/pinokio.js`, `pinokio/icon.png` (copy of PMOVES.AI `PMOVES-pinokio/assets/icon.png`), `pinokio/plugins/pmoves-claude/pinokio.js`, and `pinokio/test/plugins.test.js` (node:test, no dependencies).

- [ ] **Step 1: Write the failing test** (`pinokio/test/plugins.test.js`):
```javascript
const test = require("node:test")
const assert = require("node:assert")
const fs = require("fs")
const os = require("os")
const path = require("path")

const ROOT = path.resolve(__dirname, "..")   // PMOVES-registry/pinokio
const launcher = require(path.join(ROOT, "pinokio.js"))
const pluginDirs = fs.readdirSync(path.join(ROOT, "plugins"))
  .filter(d => fs.existsSync(path.join(ROOT, "plugins", d, "pinokio.js")))
const WRAPPER_MSG = "bash \"{{envs.PMOVES_REPO || kernel.path('api/PMOVES.AI')}}/pmoves/scripts/claude-pmoves.sh\""

test("launcher plugins array lists exactly the plugin dirs that exist", () => {
  const listed = [...launcher.plugins].sort()
  const onDisk = pluginDirs.map(d => `plugins/${d}/pinokio.js`).sort()
  assert.ok(onDisk.length >= 1, "at least one bundled plugin on disk")
  assert.deepStrictEqual(listed, onDisk, `listed=${listed.length} onDisk=${onDisk.length}`)
})

test("launcher metadata follows the example", () => {
  assert.strictEqual(launcher.version, "7.0")
  assert.strictEqual(launcher.title, "PMOVES Registry")
  assert.strictEqual(typeof launcher.menu, "function", "fail-visible menu required (Review Focus 3)")
})

for (const dir of pluginDirs) {
  const file = path.join(ROOT, "plugins", dir, "pinokio.js")
  const plugin = require(file)

  test(`${dir}: run targets the caller folder on win32 and non-win32`, () => {
    const win = plugin.run.find(s => String(s.when).includes("=== 'win32'"))
    const nix = plugin.run.find(s => String(s.when).includes("!== 'win32'"))
    assert.ok(win && nix, "win32 and non-win32 branches (Review Focus 2)")
    for (const s of plugin.run) {
      assert.strictEqual(s.method, "shell.run")
      assert.strictEqual(s.params.path, "{{args.cwd}}")
      assert.strictEqual(s.params.input, true)
    }
    assert.strictEqual(win.params.shell, "{{kernel.path('bin/miniforge/Library/bin/bash.exe')}}")
  })

  test(`${dir}: bundled plugin, not standalone`, () => {
    assert.strictEqual(plugin.path, undefined, "PINOKIO.md:2861: bundled app plugins do not need path")
  })

  test(`${dir}: no credentialed NATS URL`, () => {
    assert.doesNotMatch(fs.readFileSync(file, "utf8"), /nats:\/\/[^@{$\s"']+:[^@\s"']+@/)
  })
}

test("pmoves-claude runs the PMOVES wrapper, not upstream npx", () => {
  const plugin = require(path.join(ROOT, "plugins", "pmoves-claude", "pinokio.js"))
  for (const s of plugin.run) {
    assert.strictEqual(s.params.message, WRAPPER_MSG)
    assert.doesNotMatch(JSON.stringify(s.params), /@anthropic-ai\/claude-code|dangerously-skip-permissions/)
  }
})

test("launcher menu fails visibly when the wrapper is missing", async () => {
  process.env.PMOVES_REPO = "/definitely/not/a/repo"
  try {
    const items = await launcher.menu({ path: (...a) => path.resolve("/unused", ...a) }, {})
    assert.strictEqual(items.length, launcher.plugins.length, `items=${items.length} plugins=${launcher.plugins.length}`)
    for (const item of items) assert.match(item.text, /wrapper not found/)
    assert.match(items[0].description, /\/definitely\/not\/a\/repo\/pmoves\/scripts\/claude-pmoves\.sh/)
  } finally {
    delete process.env.PMOVES_REPO
  }
})

test("launcher menu falls back to kernel.path('api', 'PMOVES.AI') when PMOVES_REPO is unset", async () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "pinokio-home-"))
  const scripts = path.join(home, "api", "PMOVES.AI", "pmoves", "scripts")
  fs.mkdirSync(scripts, { recursive: true })
  fs.writeFileSync(path.join(scripts, "claude-pmoves.sh"), "#!/bin/sh\n")
  delete process.env.PMOVES_REPO
  const items = await launcher.menu({ path: (...a) => path.resolve(home, ...a) }, {})
  assert.strictEqual(items[0].text, "PMOVES Claude: ready")
})
```
- [ ] **Step 2: Run to verify it fails.** `node --test pinokio/test/*.test.js` → expected `Cannot find module '.../pinokio/pinokio.js'`. (A bare directory argument is resolved as a module on Node 24 and fails with MODULE_NOT_FOUND; always pass the glob.)
- [ ] **Step 3: Implement the launcher** `pinokio/pinokio.js`:
```javascript
// PMOVES Registry: Pinokio app launcher that bundles the PMOVES harness plugins.
// Plugins are declared in `plugins` (PINOKIO.md:2246-2251) and appear on /plugins.
// Plan: PMOVES.AI docs/superpowers/plans/2026-09-24-p7-playground-pinokio-plugins.md
const path = require("path")
const fs = require("fs")

const PLUGINS = [
  { dir: "pmoves-claude", title: "PMOVES Claude", wrapper: "pmoves/scripts/claude-pmoves.sh" }
]

module.exports = {
  version: "7.0",
  title: "PMOVES Registry",
  icon: "icon.png",
  description: "PMOVES harness plugins for every AGInTZ harness, plus the PMOVES ACP registry.",
  link: "https://github.com/POWERFULMOVES/PMOVES-registry",
  plugins: PLUGINS.map(p => `plugins/${p.dir}/pinokio.js`),
  menu: async (kernel, info) => {
    // kernel.path is a function resolving against PINOKIO_HOME (pinokiod kernel/index.js:550-552).
    const repo = process.env.PMOVES_REPO || kernel.path("api", "PMOVES.AI")
    return PLUGINS.map(p => {
      const wrapper = path.resolve(repo, p.wrapper)
      if (!fs.existsSync(wrapper)) {
        return {
          icon: "fa-solid fa-triangle-exclamation",
          text: `${p.title}: wrapper not found`,
          description: `Expected ${wrapper}. Set PMOVES_REPO or clone PMOVES.AI to PINOKIO_HOME/api/PMOVES.AI.`
        }
      }
      return {
        icon: "fa-solid fa-terminal",
        text: `${p.title}: ready`,
        description: `Runs ${wrapper}. Start it in any folder from Pinokio's Plugins page.`
      }
    })
  }
}
```
- [ ] **Step 4: Implement the plugin** `pinokio/plugins/pmoves-claude/pinokio.js` (shape of the built-in `system/plugin/claude/pinokio.js`, P22, with the upstream `npx` replaced by the PMOVES wrapper):
```javascript
// PMOVES Claude: bundled Pinokio terminal plugin. Runs pmoves/scripts/claude-pmoves.sh
// (node identity, Cipher agentId binding, MCP roster, damage-control) in the caller's folder.
module.exports = {
  version: "7.0",
  title: "PMOVES Claude",
  icon: "../../icon.png",
  description: "Claude Code with PMOVES node identity, Cipher binding and damage-control.",
  link: "https://github.com/POWERFULMOVES/PMOVES.AI",
  launch_type: "terminal",
  run: [{
    when: "{{platform === 'win32'}}",
    id: "run",
    method: "shell.run",
    params: {
      shell: "{{kernel.path('bin/miniforge/Library/bin/bash.exe')}}",
      conda: { skip: true },
      env: { PMOVES_PINOKIO_PLUGIN: "pmoves-claude" },
      message: "bash \"{{envs.PMOVES_REPO || kernel.path('api/PMOVES.AI')}}/pmoves/scripts/claude-pmoves.sh\"",
      path: "{{args.cwd}}",
      input: true,
      buffer: 1024
    }
  }, {
    when: "{{platform !== 'win32'}}",
    id: "run",
    method: "shell.run",
    params: {
      env: { PMOVES_PINOKIO_PLUGIN: "pmoves-claude" },
      message: "bash \"{{envs.PMOVES_REPO || kernel.path('api/PMOVES.AI')}}/pmoves/scripts/claude-pmoves.sh\"",
      path: "{{args.cwd}}",
      input: true,
      buffer: 1024
    }
  }]
}
```
The repo path comes from `PMOVES_REPO` or `kernel.path('api/PMOVES.AI')` (`PINOKIO.md:8077`), never from a chain of `..` segments, so it does not depend on where the registry launcher is installed.
- [ ] **Step 5: Run tests to verify they pass.** `node --test pinokio/test/*.test.js` → all pass; record the test count beside the result.
- [ ] **Step 6: Install into Pinokio and launch** (runbook; operator or steward, after Task 0.3's gate):
```bash
PT="$HOME/pinokio/bin/npm/bin/pterm"
"$PT" download https://github.com/POWERFULMOVES/PMOVES-registry.git   # PTERM.md §download; use --branch=feat/pinokio-harness-plugins before merge
```
Open Pinokio's `/plugins` page (the P21 method) and confirm "PMOVES Claude" is listed next to the built-ins. Start it in `~/pinokio/api/PMOVES.AI`. Expected: Claude Code starts with the claude-pmoves banner (`identity=… cipher=…` lines), and the Task 0.2 Step 3 ancestry (with `pgrep -n -f claude-pmoves`) reaches the Pinokio process and contains no `code-insiders`. The win32 branch is proven here only by the unit test; claim Windows support after a run on a Windows node, and report COULD-NOT-MEASURE until then.
- [ ] **Step 7: Commit** `pinokio/` to `feat/pinokio-harness-plugins` and open a PR against PMOVES-registry `main`.

### Task 2.2: Sidecar schema + remaining harness plugins

**Files (PMOVES-registry):** Create `pmoves/sidecar.schema.json`, `pmoves/sidecars/<id>.json` (one per harness), `pinokio/test/sidecars.test.js`, and `pinokio/plugins/pmoves-{crush,kilo,codex,kimi,hermes}/pinokio.js`; extend `PLUGINS` in `pinokio/pinokio.js`.

- [ ] **Step 1: Write the schema** `pmoves/sidecar.schema.json` (JSON Schema draft 2020-12, `additionalProperties: false`). Required fields:
  - `id`: the registry entry id when one exists (e.g. `kimi`, `kilo`), otherwise `pmoves-<harness>`.
  - `pmoves_wrapper`: path relative to the PMOVES.AI root, pattern `^pmoves/scripts/[A-Za-z0-9._-]+$` (e.g. `pmoves/scripts/crush-pmoves`).
  - `tui`: `true`.
  - `acp`: `{"command": string, "args": [string]}` or `null`.
  - `cipher_agent_id_source`: const `"signing_identity_cards.yaml"`.
  - `node_affinity`: array of node names, copied from `pmoves/config/agent_registry.yaml` in PMOVES.AI.
- [ ] **Step 2: Write the failing test** `pinokio/test/sidecars.test.js`: every `pmoves/sidecars/*.json` validates against the schema (a small stdlib validator for the six fields above, no dependencies); every sidecar's `pmoves_wrapper` equals the `script` of one `pmoves_wrappers` entry in PMOVES.AI `pmoves/configs/cli_tools.yaml` (claude-pmoves `pmoves/scripts/claude-pmoves.sh`, crush-pmoves `pmoves/scripts/crush-pmoves`, kilo-pmoves `pmoves/scripts/kilo-pmoves.sh`, codex-pmoves `pmoves/scripts/codex-pmoves.sh`, kimi-pmoves `pmoves/scripts/kimi-pmoves.sh`, hermes-pmoves `pmoves/scripts/hermes-pmoves`), held as a fixture list in the test; every plugin dir has a sidecar and every sidecar has a plugin dir; no sidecar file sits inside an upstream entry dir (`git ls-files '*/agent.json'` dirs contain no `pmoves` file). Print the sidecar and plugin counts beside the result.
- [ ] **Step 3: Write the sidecars.** `acp` values follow P27: kimi `{"command":"kimi","args":["acp"]}`, kilo `{"command":"kilo","args":["acp"]}`; claude, codex and hermes `null` until Phase 4 measures an ACP server for them; crush `null` until lane `feat/crush-acp-server` lands.
- [ ] **Step 4: Write the five plugins** as copies of `pmoves-claude/pinokio.js` with the title, `PMOVES_PINOKIO_PLUGIN` value and wrapper path changed, and add each to `PLUGINS`. Crush's plugin ships now as a TUI. It is the canonical `PMOVES-registry/pinokio/plugins/pmoves-crush/pinokio.js` that Task 1.2 reconciles against.
- [ ] **Step 5: Run** `node --test pinokio/test/*.test.js` → all pass (the launcher-lists-every-dir test now covers 6 plugins). Re-run Task 2.1 Step 6 with `pterm download` of the branch, confirm all six on `/plugins`, then move the loose `~/pinokio/plugin/pmoves-crush` aside (do not delete it) and confirm `pinokio-plugin-provenance` returns 0.

### Task 2.3: IDE desktop plugins (depends on D1)

- [ ] Only after D1 is decided. For each chosen IDE (VS Code and/or Antigravity), add `pinokio/plugins/pmoves-<ide>/pinokio.js` mirroring the built-in vscode plugin (`/opt/Pinokio/resources/app.asar.unpacked/node_modules/pinokiod/system/plugin/vscode/pinokio.js`): an `exec` step guarded by `when: "{{which('code')}}"` for VS Code (for Antigravity, the binary name is read from the installed build, not assumed) with `path: "{{args.cwd}}"`, followed by `process.wait`. On Linux the `exec` message wraps the binary in `systemd-run --user --scope -p MemoryMax=4G` (Review Focus 5; 4G is the 2.2 GB deb-code RSS from Task 0.1 Step 1, doubled and rounded down), and the PR body records the measured RSS beside the D1 decision. If D1 picks portable-pinned builds, add `install` + `installed` per `PINOKIO.md` "Installable Plugins" with an exact version pin (no `latest`). Seed per-room settings from PMOVES.AI `.vscode/settings.json` minus the credentialed `terminal.integrated.env.*` NATS_URL. Test with the same node:test file, whose per-plugin loop then branches on type: terminal plugins keep the `shell.run` assertions, and for desktop plugins it asserts that the first `run` step has `method === "exec"`, that `process.wait` follows it, and that `launch_type` is absent or `"desktop"`. Install as in Task 2.1 Step 6, then close the IDE window and re-run Task 0.2 Step 3 on a `pmoves-claude` session to confirm it survives.

### Task 2.4: Remove credentialed NATS defaults

- [ ] In PMOVES.AI, `.vscode/settings.json` `terminal.integrated.env.{windows,linux}.NATS_URL` becomes `"${env:NATS_URL}"`. Test: `git grep -nE 'nats://[^@{$ ]+:[^@ ]+@' -- .vscode` returns nothing. (The POWERFULMOVES/code fork's `pmoves-codex` is out of scope: Pinokio 8.2 does not load it, P21.)

---

## Phase 3 (outline, detailed plan after G1 = Phase 2 merged): generate plugins from the source of truth

- Add a `pinokio_plugin` renderer to `pmoves_launcher_generator.py` that emits `pmoves-<family>/pinokio.js` for every `cli_tools.yaml` `pmoves_wrappers` entry (claude, crush, kilo, codex, kimi, hermes) into a checkout of the code fork, reusing the `CliTool` / `NodeIdentity` model (P17).
- Add a drift check: the rendered output is compared with the fork's committed files, in the same style as `launchers.manifest.json`'s sha256 inventory.
- Hand-written Phase 2 plugins become the generator's golden fixtures.

## Phase 4 (outline, after G2 = Phase 3 green): PMOVES-registry + Spynel

- The generator emits `pmoves-<family>/agent.json` into PMOVES-registry, per the upstream `agent.schema.json` (`distribution.npx|binary|uvx`). `acp_registry_map.py` links each one, so the `linked` count goes above the current 1.
- Fix the dead `spynel` bridge. Restore, or supersede with a documented reason, `TAC_ACP_REGISTRY.md` (P18).
- Spynel: establish from Spynel's own docs how it discovers ACP agents (P19 found no registry key), then point it at PMOVES-registry. `make -C pmoves acp-launcher-probe` must PASS for every PMOVES entry.

## Phase 5 (outline, after G3): P7 rooms bind plugin sets

- Room manifest overlay `plugins: [pmoves-claude, pmoves-vscode, …]` (schema bump in `room.manifest.v1`), selected per `ROOMS_ON_A_STAGE.md`.
- P7 publishes `p7.nats.launch` / `p7.nats.session` when a plugin session starts or stops (P20: reserved today). Verify with a live `nats sub 'p7.nats.>'` capture during a launch.
- Closes P2 ("Route P7 launcher through room/stage selection").

## Parallel tracks (not blocking Phases 1-2)

- PMOVES-pinokio PR #11 (8.2.0 sync) → then D4 (install the fork build) → PR #12 (fleet console, spec §3 moves 1-2).
- `fleet_sentinel` deploy (spec §4) → `/registry.json` feeds PR #12's menu.
- D3: fork `pinokiocomputer/home` to pin the docs source (P15).

## Self-Review (done at authoring)

- Spec coverage: §3 moves 1-2 → Parallel tracks (PR #12). §3 move 3 (self-heal in launcher) → deferred to PR #12's successor; not covered here, called out. §Sequencing 1 (.vscode) → partially covered (Task 2.4 credentials; Task 2.2 settings seed). The remaining §1 gaps (schemas, tasks, launch, mcp.json) are NOT in this plan and stay open in the spec. P2 → Phase 5.
- Placeholders: Phases 3-5 are deliberately outlines, gated on measurements; Phases 0-2 carry full steps.
- Type consistency: `PluginReport`, `classify`, `resolve_pinokio_home`, `main` are used identically in Task 1.1 tests and implementation.
