# claude-pmoves launcher auth sanitize — LEARNINGS

This slice ships the **parent-env-side defense** for the `claude-pmoves.{sh,ps1}` launcher's auth-key hygiene, complementing the existing **file-side defense** (the blocklist that filters env.shared). The slice lands 1 commit + 1 test on `feat/claude-pmoves-launcher-auth-sanitize` (PR #3091 OPEN), 6/6 tests pass.

## Lesson 1: file-side defense ≠ parent-env-side defense

The launcher's existing blocklist — `^(ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN|ANTHROPIC_BASE_URL|CLAUDECODE|CLAUDE_CODE_|CLAUDE_SESSION_)$` — is a **file-side defense**. It filters vars coming **in from `env.shared`** (the Docker Compose env_file the launcher sources). It does NOT filter vars coming **in from the parent shell**.

The bug class: a launcher's caller (the operator's terminal, a CI step, a daemon's environment) has the auth var set in the parent shell. The launcher inherits it on the way to `exec claude`. The launcher sources env.shared through the blocklist (correct), but the inherited parent env reaches the child process anyway. Claude Code's auth precedence rule then fires the warning.

**General principle:** every defense has a SCOPE. A "block X from file Y" defense does NOT also defend "X from parent env Z". When you inherit an environment, the inherited set must be defended at the inheritance boundary, not assumed to be clean because some other source was cleaned.

The fix: explicit `unset` for the same families from the parent env, immediately before `exec claude`. The blocklist still filters env.shared; the new unset clears the parent env. Both are needed (depth-in-depth).

## Lesson 2: byte-identical semantics, byte-different mechanisms

`claude-pmoves.sh` uses `compgen -A variable` (bash builtin, returns a string-list of defined var names) plus a `for _var in $(compgen ...)` loop. `claude-pmoves.ps1` uses `[Environment]::GetEnvironmentVariables('Process').Keys` (.NET API, returns a dictionary's Keys) plus a `foreach ($key in @(...))` loop. The two mechanisms look completely different but produce the same effect.

**The lesson:** when porting code across runtimes, focus on SEMANTICS not MECHANISMS. The test asserts the .sh semantics (the .ps1 isn't tested yet — see Lesson 6). The .sh and .ps1 blocks aren't byte-identical but they ARE semantically byte-identical, and a future refactor that swaps `compgen` for `${!prefix*}` (a bash-ism) or `[Environment]::GetEnvironmentVariables('Process')` for `Get-ChildItem Env:` (another PowerShell idiom) would not change the semantics.

## Lesson 3: opt-in verbosity for operator visibility

The unset block emits a single `cleared auth vars from parent env: <list>` line on stderr. This is opt-in verbosity: silent in normal operation, visible when something was actually cleared.

**General principle:** a defensive sweep that runs every time but rarely does anything is a great place to add a "rarely does anything" log line. The operator never sees the line in clean launches; the operator ALWAYS sees it when something was wrong. This is the same pattern as `cargo build --verbose` (silent by default, verbosity opt-in), or systemd's `ConditionXYZResult=...` lines (silent on success, loud on failure).

**Anti-pattern to avoid:** silent defensive sweeps. They mask both bugs (the sweep itself is wrong) and successes (the sweep worked but the operator can't tell). A noisy-on-action log line turns the sweep into a debugging tool.

## Lesson 4: blocklist regex ≠ unset pattern

The existing blocklist uses a bash regex: `^(...)$` matched per-key. The new unset uses `compgen -A variable "${_pattern}"` which returns ALL defined vars matching the prefix. These are NOT the same operation.

**Why this matters:** the blocklist filters ONE KEY AT A TIME (it's matched inside the env.shared loop). The unset enumerates ALL DEFINED VARS in the parent env and unsets those matching the prefix. The two are necessary because they operate on different sets: the blocklist operates on the file-being-sourced, the unset operates on the parent-process-env.

**A future anti-pattern to watch for:** trying to unify the two via a single regex over both files. They have different inputs, different output shapes (a file's lines vs the shell's env table), and different semantics (skip vs unset). Forcing them into one mechanism would couple two unrelated concerns.

## Lesson 5: the test is the contract

The new test `test-launcher-auth-sanitize.sh` asserts 6 things:
1. Both launchers have the cleared-auth-vars marker
2. Both launchers have the unset sweep
3. Extracting the .sh block and running it under `env -i` with 7 auth vars pre-set clears all 7
4. The cleanup line names the cleared vars

This is the regression contract. If a future change adds a new blocklist family (e.g. `CLAUDE_AGENT_TEAM_*`), the test fails on grep (the new prefix isn't in the unset sweep) and the operator is forced to update the test. Without the test, the regression is silent — the launcher keeps launching, but with auth vars set, and the operator's terminal shows the warning again.

**General principle:** a defensive sweep is only as good as its regression contract. Without a test, the sweep is one "I forgot to update this" away from being silently wrong.

## Lesson 6: the .ps1 path isn't tested yet

The test asserts the .sh path's semantics by extracting the block and running it under `env -i`. The .ps1 path is asserted only by grep (the marker is present, the sweep uses `SetEnvironmentVariable`). The actual run-time behavior of the .ps1 unset sweep is not exercised by the test.

**This is a known gap, not a hidden one.** The test description explicitly notes "The .ps1 path isn't tested yet". A future slice should add a PowerShell test that:
- Spawns a child PowerShell process with the auth vars pre-set
- Loads the .ps1 unset block
- Verifies the child env no longer has the auth vars

`Test-Path` checks the var is defined in PowerShell; the equivalent is `[Environment]::GetEnvironmentVariable($var, 'Process') -ne $null`. The .ps1 launcher's `Test-Path "Env:$var"` is the canonical "is this env var set" check.

**Why this gap is acceptable for this slice:** the .sh test catches the SEMANTICS (does the unset sweep clear what it should); the .ps1 grep catches the PRESENCE (does the .ps1 file contain a sweep at all). Together they're a depth-2 defense — if either fails, the launcher is broken. A future slice that adds a PowerShell test closes the depth-3 layer (does the .ps1 sweep actually run as expected).

## Lesson 7: don't propose workarounds when a fix is on the way

Operator feedback (2026-09-16): when a launch fails, the operator wants the SDK fix + doc provenance, not a manual workaround they have to remember. The earlier answer proposed "unset the auth var in your shell first" as one of three options — that's a workaround for a problem the launcher should solve.

**General principle:** a workaround is acceptable as a STABILIZER (the system is broken right now, here's a temporary mitigation) but UNACCEPTABLE as a FINAL ANSWER. The launcher ships with explicit unset because the parent-env-side defense is what the system needs; the workaround only matters between "PR #3091 opens" and "operator admin-merges #3091".

This lesson is in part meta-feedback (about how to communicate a fix to the operator) and in part architectural (a defensive sweep should not require the caller to know about it). Both are durable.

## What I'd do differently next slice

- **Add the PowerShell test** as commit 2 of this slice (Lesson 6's gap). The gap is acceptable for v0; for v1, the test should be byte-symmetric with the .sh test.
- **Port the same block to crush-pmoves** in a follow-up. The .sh and .ps1 are now self-healing; crush-pmoves is not. If a Z890 operator hits the same warning, the same fix is needed there.
- **Add a `make -C pmoves launcher-self-check` target** that runs the test as part of CI. The test currently lives in `deploy/provision/tests/`; CI doesn't run it.

## Operator-visible artifacts

- **SDK:** `deploy/provision/claude-pmoves.sh` lines 75-104 (unset loop + compgen sweep + cleanup message); `deploy/provision/claude-pmoves.ps1` lines 25-49 (`[Environment]::SetEnvironmentVariable` sweep + cleanup message)
- **Test:** `deploy/provision/tests/test-launcher-auth-sanitize.sh` — 6 assertions, all pass
- **AGNOTE trail:** `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` row at `2026-09-16T17:40:00Z` (this slice's CLAIM row)
- **LEARNINGS:** this file
- **PR:** https://github.com/POWERFULMOVES/PMOVES.AI/pull/3091
