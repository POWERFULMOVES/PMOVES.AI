# PR Review Watch

Run the pr-review-watcher agent. Detect review events on watched PMOVES PRs, classify + bucket threads, fill the LEARNINGS.md draft, apply fixes (with operator gates), sign the CHIT trail, resolve via GraphQL.

## Arguments

- `$ARGUMENTS` — Optional: `--prs 2132,2133,2134`, `--mode {watch,triage,status,stop}`, `--quiet` (auto-approve all gates), `--dry-run` (simulate without touching GitHub)

## Description

The watcher is the A2UI-lane review-trim operator. It listens for new review events on the watched PMOVES PRs (default: #2132, #2133, #2143 or whatever is in the manifest at `pmoves/docs/logs/pr_open/pr_manifest_2026-07-15.json`), then walks the trim cycle with operator approval at 5 explicit gates.

**Operators approve at gates.** The agent never auto-resolves, never auto-pushes. The CHIT trail sign still records what was auto-approved (transparency for audit) but the default is to ask.

## Instructions

Parse `$ARGUMENTS` and dispatch to the pr-review-watcher agent.

### Default (no args)

Run the watcher in **watch** mode on the 3 open A2UI PRs.

1. Read `pmoves/docs/logs/pr_open/pr_manifest_2026-07-15.json` to get the watched PRs
2. Spawn the pr-review-watcher agent with:
   - `tools`: Read, Write, Edit, Bash, Grep, Glob, Agent(pr-trimmer)
   - `initialPrompt`: "watch PRs <list> for review events; ask operator at each gate"
3. The agent loops, surfacing events as they arrive

### `--triage` (most common first-pass mode)

Classify + bucket + fill LEARNINGS.md DRAFT only. **No fixes. No push. No trail sign.** The operator reviews the LEARNINGS.md before any code changes.

Use this when:
- A new review lands and you want to see what the bot said before deciding
- You want to understand the buckets before committing to a fix path
- You're on a low-risk PR and just want the learning artifact

### `--status`

Read-only health check. No gate. No PRs touched. Returns:
- watcher daemon state (PID, runtime, last event ts)
- last 5 arrivals from `pmoves/docs/logs/pr_review_arrivals.jsonl`
- conformance state for the 3 watched PRs (python tests / a2ui conformance / axe-core)
- AGNOTE trail state for the trim cycle

Use this for "what's the trim cycle doing right now?"

### `--stop`

Kill the watcher daemon if one is running. No gate (operator's intent is clear from the command).

### `--quiet` (auto-approve all gates)

Run the trim cycle end-to-end without asking. The CHIT trail sign records what was auto-approved. **NOT RECOMMENDED** for the first trim on a new PR — at minimum, Gate 1 should be human-approved so the operator can see the cycle once.

### `--dry-run` (simulation)

Run the full workflow against a synthetic event (or the last cached event from the log) without touching GitHub. Useful for:
- Testing the trim cycle on a new branch
- Training a new local model on the workflow
- Verifying the LEARNINGS template fills correctly

## The 5 operator gates (the agent asks at these)

1. **Pre-trim**: "PR #N has a new review. Start the trim cycle? [y/n/triage/stop]"
2. **Per-fix batch**: "Apply K fixes. All Legitimate. Approve batch? [all/select/skip/abort]"
3. **Conformance failure** (only if it happens): "Conformance gate FAILED. Revert? [revert/keep/manual]"
4. **Resolve + sign + push**: "Trim complete. Resolve K threads + sign trail + push. Approve? [y/hold/abort]"
5. **Special-case** (one per non-Legitimate thread): Already-fixed / Owner / Out-of-scope / Pre-existing

See `.claude/agents/pr-review-watcher.md` for the full gate prompts.

## Examples

```bash
# Default: watch the 3 A2UI PRs
/pr-review-watch

# Watch specific PRs
/pr-review-watch --prs 2132,2133,2134,2094

# Triage mode: just see the buckets, no fixes
/pr-review-watch --triage

# Health check
/pr-review-watch --status

# Stop the daemon
/pr-review-watch --stop

# Auto-approve all gates (use with care)
/pr-review-watch --quiet

# Dry run on the last event
/pr-review-watch --dry-run
```

## File references

- `.claude/agents/pr-review-watcher.md` — the agent definition (this command dispatches to it)
- `pmoves/tools/pr_review_watcher.py` — the listener (the agent runs it as a subprocess)
- `pmoves/mk/pr-review.mk` — the make targets (alternative entry point)
- `pmoves/docs/templates/PR_LEARNINGS.template.md` — the LEARNINGS template
- `pmoves/docs/operations/REVIEW_STYLE_2026-07-15.md` — the meta-doc
- `pmoves/docs/logs/pr_open/pr_manifest_2026-07-15.json` — the PR manifest (default PRs)
- `pmoves/docs/logs/pr_review_arrivals.jsonl` — the watcher event log
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — the trail / claim register

## Related

- `/pr-trim` — the older generic trim cycle (this command is the A2UI-aware successor)
- `/pr-monitor` — read-only PR state snapshot (no trim, just status)
- `make -C pmoves pr-review-watch` — the make equivalent (no agent, just the watcher)
- `make -C pmoves pr-review-trim` — direct call to `pr_hedge_trim.py` (skips the agent's classification layer)
