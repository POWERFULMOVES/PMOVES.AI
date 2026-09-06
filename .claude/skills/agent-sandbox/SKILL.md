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

Use the Make targets. They route `E2B_API_KEY` through `pmoves/scripts/with-env.sh`
(the canonical loader) so nothing is hardcoded and no credential is echoed:

```bash
make -C pmoves sandbox-preflight            # check uv + CLI + E2B_API_KEY presence (name/length only)
make -C pmoves sandbox-help                 # real command surface, straight from the CLI
make -C pmoves sandbox-create               # provision; prints the sandbox ID
make -C pmoves sandbox-exec SBX=<id> CMD='echo hello'
make -C pmoves sandbox-list
make -C pmoves sandbox-kill SBX=<id>        # tear down
make -C pmoves sandbox-smoke                # end-to-end: create -> exec -> kill
```

`SBX` is the sandbox ID. `CMD` is the command to run inside the sandbox. Extra flags go in
`ARGS`. See `pmoves/Makefile` → `sandbox-*`.

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

`E2B_API_KEY` is required. The CLI does **not** read it directly; the `e2b` SDK reads it
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

## If it does not work

Report **COULD-NOT-MEASURE** with the exact error and stop. Do not fall back to doing the
operation on the host — that is the exact failure this skill exists to prevent.
Exit-code doctrine: `0` clean / `1` findings / `3` could-not-measure. Could-not-measure is
not a pass, but it *is* an acceptable outcome.

## Self-hosting (not wired — operator decision)

`E2B_DOMAIN` is unset, so the SDK targets **e2b.dev cloud**. The fleet already owns
`PMOVES-Danger-infra` (self-hostable E2B infrastructure, `iac/`, `go.work`, `DEV-LOCAL.md`)
and `PMOVES-E2B-Danger-Room`. Pointing `E2B_DOMAIN` at self-hosted infra has cost and
topology implications and is an operator decision — do not flip it unilaterally.

## Cross-references

- `.claude/agents/delivery-agent.md` — the sanctioned-substitute rule for live mutations.
- `archon-qa-agent` (`.claude/agents/archon-qa-agent.md`) — Archon mint QA subordinate.
- `superpowers:using-git-worktrees` — git-level isolation (different layer; this is process/host isolation).
- `pmoves-mesh-preflight` skill — confirm mesh health before sandboxing against it.
- `skills/PMOVES-agent-sandbox-skill/.claude/skills/agent-sandboxes/SKILL.md` — upstream skill doc (template tiers, workflow prompts).
