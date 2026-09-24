# P7 Playground — Pinokio-Launched VS Code + PMOVES Harness Plugins: Implementation Plan and Runbook

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Pinokio launcher work additionally REQUIRES the `gepeto` skill (`~/.claude/skills/gepeto/SKILL.md`, its six-step Non-Negotiable Execution Workflow) and the `pinokio` skill (pterm-first runtime control). Room work uses the `p7-stage` skill. Recall from and store to Cipher (`pmoves-cipher-local`, agentId = your signing-card id) before and after each phase.

**Goal:** Agent sessions on a PMOVES node run under Pinokio, not inside an editor, and use PMOVES-customized harness plugins and a PMOVES-customized VS Code. Every installed plugin must be reproducible from a tracked git ref.

**Architecture:** Pinokio is the agent runtime layer. Terminal plugins (`shell.run`) own the agent sessions. A desktop plugin (`exec`) opens a pinned, portable VS Code per room. All PMOVES plugins live as subfolders of the POWERFULMOVES/code fork, which is installed as `PINOKIO_HOME/plugin/code`. That fork is rendered from the same source of truth as the existing launcher generator, `pmoves/configs/cli_tools.yaml` + `pmoves/config/agent_registry.yaml`. P7 rooms then choose which plugin set a room runs.

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

## Global Constraints

- Plugin shape mirrors `~/pinokio/prototype/system/examples/plugin_installable_agent/pinokio.js`: metadata in the root `pinokio.js`, no separate `pinokio.json`, no `install.js`/`start.js`/`reset.js`/`update.js`, and `run` targets `{{args.cwd}}` (SPEC.md Structure Rules).
- Never edit upstream checkouts. `pinokiocomputer/code` customizations go to `POWERFULMOVES/code` branch `PMOVES.AI-Edition-Hardened`, and app changes go to `POWERFULMOVES/PMOVES-pinokio`.
- Every plugin installed on a node must resolve to a tracked git ref. A hand-copied plugin is a finding (see P10).
- No absolute paths or hardcoded binaries in scripts: use `{{which('x')}}`, `{{kernel.path(...)}}`, `{{args.cwd}}` (gepeto "shell.run API").
- No credentials in committed files. `nats://nats:pmoves@…` defaults (P9, and `.vscode/settings.json` `terminal.integrated.env.*`) become `{{envs.PMOVES_NATS_URL}}` with no credentialed default.
- Tool exit codes: 0 clean / 1 findings / 3 could-not-measure. Always print the input counts beside a result.
- Harness customization is read from the P17 source of truth. Do not create a second registry.
- Live services are not touched by this plan's delivery tasks. Phase 0 runtime checks are runbook steps run by the operator or steward.

## Review Focus

1. **Pinokio itself dies:** moving sessions from the editor to Pinokio makes Pinokio the new single point of failure. The expected behaviour is that agent sessions survive an editor crash, and that a Pinokio crash is documented, not silent. Pinned by Task 0.2 step 5.
2. **Windows node:** plugins must pick bash through `shell: "{{kernel.path('bin/miniconda/Library/bin/bash.exe')}}"` (P8/P9 pattern), and wrappers must have a `.ps1` path. Pinned by Task 2.1 step 1 (the win32 branch is required by the test).
3. **Wrapper missing or repo elsewhere:** the plugin must fail visibly in its menu (the `pmoves-crush` pattern, installed `pinokio.js:37-43`), not error in a shell. Pinned by Task 2.1 step 1.
4. **Two sources for one plugin** (upstream `plugin/code/claude` next to `pmoves-claude`, or a loose `plugin/pmoves-crush` next to `plugin/code/pmoves-crush`): the provenance tool must flag the loose copy. Pinned by Task 1.1 test `test_loose_plugin_is_untracked`.
5. **Memory:** a portable VS Code per room multiplies Electron memory. On Linux each room runs under `systemd-run --user --scope -p MemoryMax=`, and the Windows gap is documented. Pinned by Task 2.2 step 1. The OOM killer has also killed docker and docker-buildx on this node (P12), so image builds must not run while an editor's memory is unbounded.

## Operator Decisions (gates; each task below names the decision it depends on)

- **D1: VS Code channel for the portable build.** Default: Insiders (current usage). Alternative: Stable.
- **D2: Plugin names and home.** Default: subfolders `pmoves-claude`, `pmoves-vscode`, `pmoves-crush` of the POWERFULMOVES/code fork, following the `pmoves-codex` precedent (P8).
- **D3: Docs pin.** Default: fork `pinokiocomputer/home` as `POWERFULMOVES/PMOVES-pinokio-home`, so the docs source (P15) is pinned. `Pmoves-program.pinokio.computer` is left stale.
- **D4: Pinokio build.** Default: keep the upstream 8.2.0 .deb (P6) through Phase 2, and switch to the PMOVES-pinokio build after PR #11 merges.

## File Structure

| Path | Repo | Responsibility | Phase |
|------|------|----------------|-------|
| `pmoves/tools/pinokio_plugin_provenance.py` | PMOVES.AI | Classify each installed plugin as fork / upstream / dirty / untracked / unmeasured | 1 |
| `pmoves/tools/tests/test_pinokio_plugin_provenance.py` | PMOVES.AI | unittest suite for the above | 1 |
| `pmoves/mk/pinokio.mk` + `include mk/pinokio.mk` in `pmoves/Makefile` | PMOVES.AI | `pinokio-plugin-provenance`, `pinokio-plugins-install` targets | 1 |
| `pmoves-claude/pinokio.js`, `pmoves-claude/icon.svg` | POWERFULMOVES/code | Terminal plugin → `pmoves/scripts/claude-pmoves.sh` | 2 |
| `pmoves-crush/pinokio.js` | POWERFULMOVES/code | Replaces the loose `plugin/pmoves-crush` (P10) | 2 |
| `pmoves-vscode/pinokio.js` | POWERFULMOVES/code | Installable desktop plugin: portable VS Code, one data dir per room | 2 |
| `pmoves/tools/pmoves_launcher_generator.py` (renderer `pinokio_plugin`) | PMOVES.AI | Emit fork subfolders from cli_tools.yaml | 3 |
| PMOVES-registry `pmoves-*/agent.json` | PMOVES-registry | ACP entries for PMOVES harnesses | 4 |
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
- [ ] **Step 2: Decide which copy is canonical.** Each hunk the installed copy adds must be carried into Task 2.3's fork subfolder or dropped with a stated reason in the PR body. Nothing is deleted from the node until Task 2.3 is installed and the provenance tool reports `fork` for it.

---

## Phase 2: PMOVES plugins in the POWERFULMOVES/code fork (depends on G0, D1, D2)

Work in a clone of `POWERFULMOVES/code` on a branch off `PMOVES.AI-Edition-Hardened`. Follow gepeto's six steps. Example lock-in: `~/pinokio/prototype/system/examples/plugin_installable_agent/pinokio.js`. The fork precedent for PMOVES env is `pmoves-codex/pinokio.js`.

### Task 2.1: `pmoves-claude` terminal plugin

**Files:** Create `pmoves-claude/pinokio.js`, `pmoves-claude/icon.svg` (copy `pmoves-codex/icon.svg`), and `test/pmoves-claude.test.js` (node:test, no dependencies).

- [ ] **Step 1: Write the failing test** (`test/pmoves-claude.test.js`):
```javascript
const test = require("node:test")
const assert = require("node:assert")
const plugin = require("../pmoves-claude/pinokio.js")

test("metadata follows the installable-plugin example", () => {
  assert.strictEqual(plugin.version, "7.0")
  assert.strictEqual(plugin.title, "PMOVES Claude")
  assert.ok(typeof plugin.menu === "function", "fail-visible menu required (Review Focus 3)")
})

test("run targets the caller folder on both platforms", () => {
  const run = plugin.run
  assert.strictEqual(run.length, 2)
  const win = run.find(s => String(s.when).includes("=== 'win32'"))
  const nix = run.find(s => String(s.when).includes("!== 'win32'"))
  assert.ok(win && nix, "win32 and non-win32 branches (Review Focus 2)")
  for (const s of run) {
    assert.strictEqual(s.method, "shell.run")
    assert.strictEqual(s.params.path, "{{args.cwd}}")
    assert.strictEqual(s.params.input, true)
    assert.ok(!/nats:\/\/[^@{]+@/.test(JSON.stringify(s.params)), "no credentialed NATS URL")
  }
  assert.match(win.params.shell, /bash\.exe/)
})

test("menu fails visibly when the wrapper is missing", async () => {
  const kernel = { path: require("path") }
  process.env.PMOVES_REPO = "/definitely/not/a/repo"
  const items = await plugin.menu(kernel, {})
  delete process.env.PMOVES_REPO
  assert.strictEqual(items.length, 1)
  assert.match(items[0].text, /wrapper not found/)
})

test("fallback path reaches PINOKIO_HOME/api/PMOVES.AI from plugin/code/pmoves-claude", async () => {
  const fs = require("fs"), os = require("os"), path = require("path")
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "pinokio-home-"))
  const pluginDir = path.join(home, "plugin", "code", "pmoves-claude")
  fs.mkdirSync(pluginDir, { recursive: true })
  fs.copyFileSync(path.join(__dirname, "..", "pmoves-claude", "pinokio.js"), path.join(pluginDir, "pinokio.js"))
  const scripts = path.join(home, "api", "PMOVES.AI", "pmoves", "scripts")
  fs.mkdirSync(scripts, { recursive: true })
  fs.writeFileSync(path.join(scripts, "claude-pmoves.sh"), "#!/bin/sh\n")
  delete process.env.PMOVES_REPO
  const installed = require(path.join(pluginDir, "pinokio.js"))
  const items = await installed.menu({ path }, {})
  assert.strictEqual(items[0].text, "Start PMOVES Claude")
  const tpl = installed.run[1].params.message
  assert.ok(tpl.includes("path.resolve(cwd, '../../../api/PMOVES.AI')"), "template depth matches the installed layout")
})
```
- [ ] **Step 2: Run to verify it fails.** `node --test test/pmoves-claude.test.js` → expected `Cannot find module '../pmoves-claude/pinokio.js'`.
- [ ] **Step 3: Implement** `pmoves-claude/pinokio.js`:
```javascript
// PMOVES Claude: Pinokio terminal plugin. Runs pmoves/scripts/claude-pmoves.sh
// (node identity, Cipher agentId binding, MCP roster, node-steward default)
// in the caller's folder. Plan: PMOVES.AI docs/superpowers/plans/2026-09-24-p7-playground-pinokio-plugins.md
const path = require("path")
const fs = require("fs")

const repoOf = () => process.env.PMOVES_REPO || path.resolve(__dirname, "../../../api/PMOVES.AI")
const wrapperOf = () => path.resolve(repoOf(), "pmoves/scripts/claude-pmoves.sh")

module.exports = {
  version: "7.0",
  title: "PMOVES Claude",
  icon: "icon.svg",
  description: "Claude Code with PMOVES node identity, Cipher binding and MCP roster.",
  link: "https://github.com/POWERFULMOVES/PMOVES.AI",
  menu: async (kernel, info) => {
    const wrapper = wrapperOf()
    if (!fs.existsSync(wrapper)) {
      return [{
        icon: "fa-solid fa-triangle-exclamation",
        text: "PMOVES Claude wrapper not found",
        description: `Expected ${wrapper}. Set PMOVES_REPO or clone PMOVES.AI to PINOKIO_HOME/api/PMOVES.AI.`
      }]
    }
    return [{ icon: "fa-solid fa-terminal", text: "Start PMOVES Claude", href: "pinokio.js" }]
  },
  run: [{
    when: "{{platform === 'win32'}}",
    id: "run",
    method: "shell.run",
    params: {
      shell: "{{kernel.path('bin/miniconda/Library/bin/bash.exe')}}",
      conda: { skip: true },
      env: { PMOVES_PINOKIO_PLUGIN: "pmoves-claude" },
      message: "bash \"${PMOVES_REPO:-{{path.resolve(cwd, '../../../api/PMOVES.AI')}}}/pmoves/scripts/claude-pmoves.sh\"",
      path: "{{args.cwd}}",
      input: true
    }
  }, {
    when: "{{platform !== 'win32'}}",
    id: "run",
    method: "shell.run",
    params: {
      env: { PMOVES_PINOKIO_PLUGIN: "pmoves-claude" },
      message: "bash \"${PMOVES_REPO:-{{path.resolve(cwd, '../../../api/PMOVES.AI')}}}/pmoves/scripts/claude-pmoves.sh\"",
      path: "{{args.cwd}}",
      input: true
    }
  }]
}
```
Note on the path: the fork is installed at `PINOKIO_HOME/plugin/code`, so this subfolder is `PINOKIO_HOME/plugin/code/pmoves-claude`. Three `..` segments reach `PINOKIO_HOME`, and `api/PMOVES.AI` is appended from there. Verify this against a real install in Step 5; do not assume it.
Depth check: the three .. segments are correct only because the fork is installed at plugin/code; the fourth test pins this by building that layout in a temp dir. A standalone install at plugin/pmoves-claude would need two. An independent verifier raised this on 2026-09-24; it was resolved by the layout, and the missing test was added.
- [ ] **Step 4: Run tests to verify they pass.** `node --test test/*.test.js` → all 4 pass. (A bare directory argument, `node --test test/`, is resolved as a module on Node 24 and fails with MODULE_NOT_FOUND. Verified 2026-09-24.)
- [ ] **Step 5: Install from the fork and launch through Pinokio** (runbook; operator or steward):
```bash
PT="$HOME/pinokio/bin/npm/bin/pterm"
mv "$HOME/pinokio/plugin/code" "$HOME/pinokio/plugin/code.upstream-$(date +%F)"   # keep, do not delete
"$PT" download https://github.com/POWERFULMOVES/code.git code --branch=<your-feature-branch>   # PTERM.md §download :270-303; switch to PMOVES.AI-Edition-Hardened after merge
python3 "$HOME/pinokio/api/PMOVES.AI/pmoves/tools/pinokio_plugin_provenance.py"         # expect: fork code
"$PT" start "$HOME/pinokio/plugin/code/pmoves-claude/pinokio.js" -- --cwd="$HOME/pinokio/api/PMOVES.AI"
```
Expected: Claude Code starts with the claude-pmoves banner (`identity=… cipher=…` lines), and the Task 0.2 Step 3 ancestry shows Pinokio as the ancestor.
- [ ] **Step 6: Commit** `pmoves-claude/` and `test/` to the fork branch, and open a PR against `PMOVES.AI-Edition-Hardened`.

### Task 2.2: `pmoves-vscode` installable desktop plugin (depends on D1)

- [ ] **Step 1: Write the failing test** `test/pmoves-vscode.test.js`: assert `path === "plugin"` is ABSENT (bundled subfolder, per PINOKIO.md:2861 "Bundled app plugins do not need this field"); assert that `install` pins an exact version (the URL contains no `latest`); assert `installed` is an async function; assert that `run` on Linux wraps the binary in `systemd-run --user --scope -p MemoryMax=` (Review Focus 5); assert `run` passes `--user-data-dir` and `--extensions-dir` under a per-room folder derived from `{{args.room || 'default'}}`; assert `launch_type === "desktop"`.
- [ ] **Step 2: Implement** by mirroring the Installable Plugins example (`PINOKIO.md` "Installable Plugins", the `install` + `installed` pattern). `install` uses `fs.download` of the pinned portable archive for `{{platform}}`/`{{arch}}`, extracts it into `{{dirname}}/dist`, and creates `{{dirname}}/dist/data` (portable mode). `run` uses `exec` with the pinned binary and per-room dirs `{{dirname}}/rooms/{{args.room || 'default'}}/{user-data,extensions}`. The version pin and download URL are recorded in the PR body together with the D1 decision.
- [ ] **Step 3: Seed per-room settings** from PMOVES.AI `.vscode/settings.json` minus the credentialed `terminal.integrated.env.*` NATS_URL (Global Constraints), plus an extension manifest that includes the theme the settings reference (`zhuangtongfa.material-theme`, missing on both installs at measurement time).
- [ ] **Step 4: Test, install, launch** as in Task 2.1 Steps 4-5; then kill the VS Code window and re-run Task 0.2 Step 3 on a `pmoves-claude` session to confirm it survives.

### Task 2.3: Move `pmoves-crush` into the fork

- [ ] Port the canonical copy decided in Task 1.2 to `pmoves-crush/pinokio.js` in the fork (plugin shape per Global Constraints: fold `start.js` into `run`). Test it the same way as Task 2.1. After install, move the loose `~/pinokio/plugin/pmoves-crush` aside (do not delete it) and confirm `pinokio-plugin-provenance` returns 0.

### Task 2.4: Remove credentialed NATS defaults

- [ ] In the fork, `pmoves-codex/pinokio.js:23,43` becomes `"{{envs.PMOVES_NATS_URL || ''}}"`. In PMOVES.AI, `.vscode/settings.json` `terminal.integrated.env.{windows,linux}.NATS_URL` becomes `"${env:NATS_URL}"`. Test: `git grep -nE 'nats://[^@{$ ]+:[^@ ]+@' -- .vscode pmoves-codex` returns nothing.

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
