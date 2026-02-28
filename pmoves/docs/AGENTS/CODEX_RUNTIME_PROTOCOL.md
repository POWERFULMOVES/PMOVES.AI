# Codex Runtime Protocol (Focus + Scout)
_Last updated: 2026-02-15_

This document defines how Codex should operate in PMOVES production-audit mode.
It is intended to be referenced by operator prompts and tooling docs.

## Operating modes

1. `focus` mode
- Use when editing code, running migrations, touching CI/security, or changing boot order.
- Chat remains minimal while execution is active.
- Every conclusion must be backed by direct command evidence.

2. `open-chat+scout` mode
- Use when strategy is still forming or risk is high/unknown.
- Keep chat open while a scout pass gathers context.
- Scout pass must return: knowns, unknowns, risks, and concrete validation commands.

Codex should explicitly signal mode in progress updates:
- `mode=focus` when heads-down implementation is active.
- `mode=open-chat+scout` when exploratory context gathering is active.

## Confidence gates (never go in blind)

Before implementation starts, require both:
- `Knowns`: facts verified from repo state, logs, or official docs.
- `Unknowns`: unresolved items with a planned validation step.

Use this checklist per task:
1. Define scope and blast radius.
2. Collect local evidence (files, logs, CI output, service state).
3. Mark unknowns and assign a verification command.
4. Proceed only when unknowns have a validation path.

## Subagent scouting pattern

Use subagent/scout passes for large tasks:
1. `Scout A`: code/compose/boot-order topology.
2. `Scout B`: CI/review comments/failing checks.
3. `Scout C`: security/secrets/credential flow.
4. `Scout D`: docs parity vs implementation reality.

Then merge findings into one execution queue:
- `P0` block release
- `P1` required before merge
- `P2` follow-up

## Validation standard

For every substantial change, include evidence for:
- build/bring-up behavior
- smoke checks relevant to touched services
- security posture impact (especially secrets handling)
- cross-platform behavior (PowerShell + bash/WSL path)

Evidence format:
- command
- result summary
- pass/fail
- next action if fail

## PR Review Sweep (Merge Gate)

Before merge or promotion:
1. Run `make -C pmoves pr-monitor`.
2. Inspect:
   - `pmoves/docs/logs/pr_monitor_latest.json`
   - `pmoves/docs/logs/pr_monitor_learnings_latest.md`
3. Address actionable comments (including out-of-diff review findings) in atomic commits.
4. Re-run `make -C pmoves pr-monitor-strict` and require exit code `0` before merge.

Nitpicks are cataloged for follow-up. Blocking actionable comments are merge blockers; out-of-diff line comments stay in the learnings queue unless they escalate into blocking feedback. Bot actionable comments only block when marked `P0`/`P1`.

## Token/time estimate handshake

For long-running tasks, Codex should provide:
- estimated work slices
- expected validation duration
- whether it is safe to keep chat open during execution

Template:
- `estimate`: short / medium / long
- `mode`: focus or open-chat+scout
- `next evidence checkpoint`: command or artifact to expect

## PMOVES-specific production notes

- Production audit is local-first and hardened-first.
- No optional service assumptions: all required submodules/services are in-scope.
- Secrets must never be committed; tracked env files must remain placeholders.
- Geometry Bus + CHIT + EvoSwarm flows must preserve observability and replayability.
