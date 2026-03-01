# CHIT Review Sweep

Post-review handshake that feeds Claude's PR review findings into the CHIT/FlOO$ pipeline. Run this after completing review work to sync learnings into the Graphiti trail.

## Arguments

- `$ARGUMENTS` - Optional: `--dry-run` to preview without writing, `--no-nats` to skip NATS publish, `--trail` to also write a Graphiti trail entry

## Instructions

This command implements the KRISS KROSS Accord scout role: Claude reviews, encodes findings as CGP, and hands off to Codex's `pr-monitor-graphiti-chit` pairing.

### Step 1: Collect PR state

Run `make -C pmoves pr-monitor` to produce:
- `pmoves/docs/logs/pr_monitor_latest.json`
- `pmoves/docs/logs/pr_monitor_learnings_latest.md`

If the command fails (missing script or Make target), report the error and stop — do not improvise a replacement.

### Step 2: Encode as CGP

Run `make -C pmoves pr-monitor-chit-packet` to produce:
- `pmoves/docs/logs/pr_monitor_learnings_latest.cgp.json`

Read the CGP packet and summarize: schema version, contributor count, encoded learnings count.

### Step 3: Trail entry (if `--trail` flag)

If `--trail` is specified, prepend a Graphiti trail entry to `docs/AGENT_TRAIL.md` using Claude's signature:

```markdown
<!-- graphiti:claude-opus phase:review-sweep ts:{current ISO-8601} -->

## ◆ Claude Opus — review-sweep: PR Review Learnings Sync

<table><tr><td style="background:#7C3AED;width:24px"></td><td>

**Resonance:** security-audit, cross-repo-orchestration
**Voice:** analytical

### Done
- {list items reviewed/merged/fixed}

### Left Behind
- {items remaining for next agent}

### For Next Agent
- CGP packet at `pmoves/docs/logs/pr_monitor_learnings_latest.cgp.json`
- Run `/chit:floos validate pr-monitor-graphiti-chit` to verify pipeline

</td></tr></table>

<!-- /graphiti -->
```

### Step 4: NATS publish (unless `--no-nats` or `--dry-run`)

Attempt to publish `ops.pr.review.completed.v1` to NATS with payload:
```json
{
  "agent_id": "claude-opus",
  "glyph": "◆",
  "color": "#7C3AED",
  "timestamp": "{ISO-8601}",
  "artifact": "pmoves/docs/logs/pr_monitor_learnings_latest.cgp.json",
  "summary": "{brief description of what was reviewed}"
}
```

Use `nats pub` if available, otherwise skip gracefully with a note that NATS is not connected.

### Step 5: Summary output

Display:
- PRs reviewed/merged in this session
- Learnings encoded (actionable vs nitpick vs out-of-diff)
- CGP packet location
- Trail entry status (written / skipped)
- NATS publish status (sent / skipped / unavailable)

If `--dry-run`, show what would be written/published without executing.

## Examples

```bash
# Standard post-review sweep
/chit:review-sweep

# Include trail entry
/chit:review-sweep --trail

# Preview without side effects
/chit:review-sweep --dry-run

# Skip NATS (offline mode)
/chit:review-sweep --trail --no-nats
```

## Related

- `/pr-monitor` — Collect PR state and learnings
- `/chit:floos validate pr-monitor-graphiti-chit` — Validate the full pipeline
- `/chit:encode` — Manual CGP encoding
- `/github:pr-review` — Review a specific PR
