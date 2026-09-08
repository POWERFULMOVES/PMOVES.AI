---
name: agent-sandbox
description: Manage isolated execution environments for agents — provision a sandbox, run a task in it, capture outputs, tear down cleanly. Use when running untrusted code, proving a fix that would otherwise require a live mutation against production, testing newly minted agents from Archon's factory, or verifying skill compositions without touching the host environment. Sourced from skills/PMOVES-agent-sandbox-skill/ (fork of disler/agent-sandbox-skill).
---

# Agent-Sandbox Skill

Isolated E2B sandboxes for PMOVES agents. **This file names the entrypoint** — do not
go hunting. The runnable CLI lives four directories deeper than the submodule root, under
a *nested* `.claude/skills/` path that is easy to miss:

```
skills/PMOVES-agent-sandbox-skill/.claude/skills/agent-sandboxes/sandbox_cli/
```

There is **no** `SKILL.md` at the submodule root. The only `SKILL.md` in that submodule is
`skills/PMOVES-agent-sandbox-skill/.claude/skills/agent-sandboxes/SKILL.md`, and the
submodule `README.md` describes the value proposition and a `.env` layout but never names
the entrypoint. That gap is why this file now carries the invocation.

## Known Road (preferred)

Use the Make targets. They route credentials through `pmoves/scripts/with-env.sh`
(the canonical loader) so nothing is hardcoded and no credential is echoed:

```bash
make -C pmoves sandbox-runbook              # owning node + every path in this lane
make -C pmoves sandbox-mode                 # which deployment mode am I resolved to?
make -C pmoves sandbox-host-probe           # is THIS node fit to self-host? (read-only)
make -C pmoves sandbox-preflight            # uv + CLI + the SELECTED mode's credential SHAPES
make -C pmoves sandbox-help                 # real command surface, straight from the CLI
make -C pmoves sandbox-create               # provision; prints the sandbox ID
make -C pmoves sandbox-exec SBX=<id> CMD='echo hello'
make -C pmoves sandbox-list
make -C pmoves sandbox-kill SBX=<id>        # tear down
make -C pmoves sandbox-smoke                # end-to-end: create -> exec -> kill
```

`SBX` is the sandbox ID. `CMD` is the command to run inside the sandbox. Extra flags go in
`ARGS`. See `pmoves/Makefile` → `sandbox-*`.

`sandbox-preflight` checks **shape**, not presence: prefix + charset + per-mode length.
`[ -n "$VAR" ]` passes a truncated secret — see the B850 blocker below, where a *longer*
than expected value sailed through every presence gate.

> **`make` cannot carry the exit-code doctrine.** GNU make exits **2** for any recipe
> failure. Measured with a control: recipes exiting 1 and exiting 3 both make `make` exit
> 2, while the script run directly returns 3 — so "findings" and "could-not-measure" are
> indistinguishable through make. The targets print their real code. Anything that
> *branches* on it must call the script directly:
> ```bash
> bash pmoves/scripts/sandbox_smoke.sh;          echo "exit=$?"
> bash pmoves/scripts/probe_danger_room_host.sh; echo "exit=$?"
> ```

## Direct invocation

The CLI is a `uv` package (`requires-python >=3.12`, `[tool.uv] package = true`) exposing
the `sbx` script. Run it from the CLI directory:

```bash
cd skills/PMOVES-agent-sandbox-skill/.claude/skills/agent-sandboxes/sandbox_cli
uv run sbx --help
```

`uv` is the intended runner — the submodule README specifies Python >= 3.12 + uv, and
`uv.lock` is committed. Do not `pip install` it into a host environment.

### Credentials

**Which** credentials are required depends on the deployment mode — see "Three deployment
modes" below; `E2B_API_KEY` alone is only sufficient for `cloud`. Both `E2B_API_KEY` and
`E2B_ACCESS_TOKEN` are funnel-managed (registered in
`pmoves/tools/chit_manifest_register.py`, delivered to `env.tier-agent`); the URLs,
`E2B_DEBUG` and `E2B_DOMAIN` are routing config and live in `env.shared`.

The CLI does **not** read credentials directly; the `e2b` SDK reads them
from the process environment. `src/main.py` calls
`load_dotenv(<submodule-root>/.env)` as a fallback — and `python-dotenv` does **not**
override values already exported — so an exported `E2B_API_KEY` always wins. Prefer
exporting it via `pmoves/scripts/with-env.sh` (what the Make targets do) over writing a
`.env`. Never print or commit the value.

## Real command surface

Verified by reading `src/main.py` and `src/commands/*.py` — these are the actual commands
and flags, not a paraphrase.

**Top level:** `sbx init`, `sbx sandbox`, `sbx files`, `sbx exec`, `sbx browser`

| Command | Purpose |
|---------|---------|
| `sbx init [-t TEMPLATE] [--timeout N] [-e K=V] [-n NAME]` | Create a sandbox and print its ID (convenience wrapper) |
| `sbx sandbox create [-t TEMPLATE] [--timeout N] [-e K=V] [-m K=V] [--auto-pause]` | Create a sandbox |
| `sbx sandbox list [-l LIMIT]` | List running sandboxes |
| `sbx sandbox info SANDBOX_ID` | Sandbox details |
| `sbx sandbox status SANDBOX_ID` | Is it running |
| `sbx sandbox connect SANDBOX_ID [--timeout N]` | Attach to an existing sandbox |
| `sbx sandbox extend-lifetime SANDBOX_ID SECONDS` | Add time |
| `sbx sandbox pause SANDBOX_ID` | Pause (beta) |
| `sbx sandbox get-host SANDBOX_ID -p PORT` | Public hostname for an exposed port |
| `sbx sandbox kill SANDBOX_ID` | **Tear down** |
| `sbx exec SANDBOX_ID COMMAND [--cwd D] [--user U\|--root] [--shell] [-e K=V] [--timeout N] [--background] [--stdin]` | Run a command inside the sandbox |
| `sbx files ls SANDBOX_ID [PATH] [-d DEPTH]` | List files |
| `sbx files read/write/edit/exists/info/rm/mkdir/mv SANDBOX_ID PATH ...` | File ops |
| `sbx files upload SANDBOX_ID LOCAL REMOTE` / `download SANDBOX_ID REMOTE LOCAL` | Binary-safe transfer |
| `sbx files download-dir` / `upload-dir` | Directory transfer |
| `sbx browser ...` | Browser automation |

Notes that bite if you skip them:
- `exec` takes the command as a **single argument** — quote it. Use `--shell` for pipes,
  redirections and wildcards.
- Prefer `--cwd` over an embedded `cd`.
- `browser` drives a **local** Chrome over CDP (playwright, a dev dependency), not a
  browser inside the sandbox. It is not part of the isolation guarantee.
- Sandboxes auto-expire on their timeout, but **kill them explicitly** when you are done.

## Minimal end-to-end

```bash
cd skills/PMOVES-agent-sandbox-skill/.claude/skills/agent-sandboxes/sandbox_cli
uv run sbx init --timeout 300 --name proof     # capture the printed Sandbox ID
uv run sbx exec <SANDBOX_ID> 'echo hello-from-sandbox'
uv run sbx sandbox kill <SANDBOX_ID>
```

Capture the sandbox ID into your context. Do not stash it in a shell variable across
tool calls — a killed session loses it and leaks a running sandbox.

## When Claude should invoke this

- **Proving a fix that would otherwise require a live mutation.** This is the primary
  case. If verifying your change means revoking a token, deleting a record, or writing to
  a production service, provision a sandbox and prove it there. See
  `.claude/agents/delivery-agent.md` → "Proving a fix that needs a live mutation".
- Running a newly minted agent's first execution against a known-good fixture.
- Testing a candidate skill composition without touching the live mesh.
- Reproducing an incident in isolation.
- Executing untrusted or generated code.

## Known blocker on B850/Knuckles (2026-09-06): malformed E2B_API_KEY

`make -C pmoves sandbox-preflight` currently reports **MALFORMED** on this node and
provisioning returns:

```
401: Unauthorized ... API key is malformed: expected the "e2b_" prefix
```

Measured shape of the delivered value (value never printed): **42 chars, begins `b_`,
followed by exactly 40 lowercase hex chars.** E2B's canonical format is `e2b_` + 40 hex =
**44 chars**. The delivered value is that string with its leading `e2` missing — a
two-character truncation somewhere in secrets delivery, not a wrong or expired key.

Positive control confirming the rest of the road is healthy: substituting a *fabricated*
well-formed key (`e2b_` + 40 zeros, registered nowhere) changes the error to
`Invalid API key ... Cannot get the team for the given API key`. A different error at a
later stage proves the CLI, the uv environment, the network path and the E2B API are all
reachable and working — **the credential is the only blocker.**

**Operator action:** re-deliver `E2B_API_KEY` through the secrets funnel with the leading
`e2` intact, then `make -C pmoves sandbox-smoke` should go green. Agents must not
reconstruct or patch the key themselves.

## If it does not work

Report **COULD-NOT-MEASURE** with the exact error and stop. Do not fall back to doing the
operation on the host — that is the exact failure this skill exists to prevent.
Exit-code doctrine: `0` clean / `1` findings / `3` could-not-measure. Could-not-measure is
not a pass, but it *is* an acceptable outcome.

## Three deployment modes — do not generalise from one page

**This section replaced an earlier one that was wrong.** It said "`E2B_DOMAIN` is unset,
so the SDK targets e2b.dev cloud... pointing `E2B_DOMAIN` at self-hosted infra" — treating
`E2B_DOMAIN` as *the* self-host switch. It is not. `E2B_DOMAIN` is the **GCP** self-host
variable; the **local** self-host stack does not use it at all, and setting it locally
misroutes every sandbox host the SDK builds. Reading one vendor page and generalising it
to another mode produced two wrong wirings on this lane before it was caught, which is
why all three modes are now on one page.

| Mode | Required | Vendor source |
|---|---|---|
| `cloud` | `E2B_API_KEY` (`e2b_` + 40 hex) | e2b.dev docs |
| `selfhost-gcp` | `E2B_ACCESS_TOKEN` (`sk_e2b_` + 32 hex) **+ `E2B_DOMAIN`** | `PMOVES-Danger-infra/self-host.md` |
| `selfhost-local` | `E2B_API_KEY` + `E2B_ACCESS_TOKEN` + `E2B_API_URL` + **`E2B_DEBUG=true`**, and **no `E2B_DOMAIN`** | `PMOVES-Danger-infra/DEV-LOCAL.md` |

The mode is **explicit and selectable**. Default is `selfhost-local` (operator decision,
2026-09-06 — self-host is approved; cloud remains reachable as a fallback):

```bash
make -C pmoves sandbox-mode                          # what am I pointed at, and why
make -C pmoves sandbox-preflight E2B_MODE=cloud
make -C pmoves sandbox-preflight E2B_MODE=selfhost-gcp
make -C pmoves sandbox-preflight E2B_MODE=selfhost-local
make -C pmoves sandbox-preflight E2B_MODE=auto       # infer from which vars are set
```

`pmoves/scripts/e2b_mode.sh` is the single place that knows the three sets. Two traps it
encodes, neither of which the vendor dotenv block states:

- **`E2B_DEBUG=true` is REQUIRED for `selfhost-local`.** The pinned e2b python SDK (2.6.4)
  only returns `localhost:{port}` hosts when debug is set (`e2b/sandbox/main.py:198`) and
  picks `http://` over `https://` off the same flag (`:49`). Without it the SDK builds
  `https://49983-<id>.e2b.app` and silently talks to the wrong place. Mode selection
  exports it.
- **`E2B_ENVD_API_URL` has no consumer at our pins.** Grep counts with a positive control:
  in the SDK monorepo `E2B_API_KEY` matches 24 files, `E2B_DOMAIN` 17, `E2B_ACCESS_TOKEN`
  10, `E2B_ENVD_API_URL` **0**; in `PMOVES-Danger-infra` it matches only `DEV-LOCAL.md`
  itself. Set it for vendor/JS parity, but do not treat setting it as having wired envd.

### Self-hosting: owning node is `pmoves-5090`

Bring-up is an **operator action on one named node**, not "someone". Full runbook —
requirements, the twelve `DEV-LOCAL.md` steps with their traps, the nine services
`make local-infra` starts, the port table and the `:3000` collision risk:

**`pmoves/docs/operations/E2B_SELF_HOST_RUNBOOK.md`**

The blocker to resolve first: `tailscale status` reports `pmoves-5090` as **windows**,
and `DEV-LOCAL.md` requires Linux because Firecracker is a KVM VMM and `nbd`/hugepages
are kernel features. Probe before assuming a shape — read-only, provisions nothing:

```powershell
powershell -ExecutionPolicy Bypass -File pmoves\scripts\probe_danger_room_host.ps1  # Windows host half
```
```bash
wsl -d <distro> -- bash pmoves/scripts/probe_danger_room_host.sh                     # Linux half
```

## Cross-references

- `.claude/agents/delivery-agent.md` — the sanctioned-substitute rule for live mutations.
- `archon-qa-agent` (`.claude/agents/archon-qa-agent.md`) — Archon mint QA subordinate.
- `superpowers:using-git-worktrees` — git-level isolation (different layer; this is process/host isolation).
- `pmoves-mesh-preflight` skill — confirm mesh health before sandboxing against it.
- `skills/PMOVES-agent-sandbox-skill/.claude/skills/agent-sandboxes/SKILL.md` — upstream skill doc (template tiers, workflow prompts).
