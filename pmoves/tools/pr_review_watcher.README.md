# `pr_review_watcher.py` — listen for GitHub review events (no polling)

> A-mode "no polling" tool for the Mavis-5090 review-trim cycle. Wraps
> GitHub's notification system in a long-running listener that surfaces
> review events the moment they arrive. When the n8n webhook bridge is
> up (B mode), the same tool switches to NATS subscription — same CLI,
> same events, no behavior change at the consumer.

## Why this exists

DARKXSIDE (2026-07-15): *"github sends notifications why not listen for those this way no need to poll"*.

Before this tool, the Mavis-5090 review-trim cycle assumed periodic `gh pr list` polls to detect when reviews came in. That's wasteful — GitHub already pushes notifications; we just need to listen.

This tool uses **HTTP conditional GET (ETag)** against `gh api /notifications`. When nothing has changed, GitHub returns 304 instantly. When a new notification appears, GitHub returns 200 with the payload. The cost of "listening" is essentially zero until something happens.

## Modes

| mode | when to use | transport |
|---|---|---|
| **`notifications`** (default) | Always-on listening for any new PR notification | `gh api /notifications` + ETag |
| `pr-watch` | Specifically watch a PR's review state (reviewDecision, latestReviews, comments) | `gh pr view --json` polling loop with diff |
| `nats` | When the n8n webhook bridge is up (B mode) — same CLI, no polling at all | NATS subscription to `github.webhook.review.*` |

## Usage

### Listen for any new PR notification (the "just listen" mode)

```bash
python pmoves/tools/pr_review_watcher.py \
    --mode notifications \
    --prs 2132,2133,2134 \
    --max-runtime 24h \
    --log pmoves/docs/logs/pr_review_arrivals.jsonl
```

Exits `0` the moment a notification for one of the watched PRs arrives, `1` on timeout, `2` on error, `130` on SIGINT.

### Per-PR review state watch (more precise than notifications)

```bash
python pmoves/tools/pr_review_watcher.py \
    --mode pr-watch \
    --pr 2132 \
    --interval 60 \
    --max-runtime 8h \
    --log pmoves/docs/logs/pr_review_arrivals.jsonl \
    --emit-nats
```

Emits when `reviewDecision`, `state`, `latestReviews` count, or `comments` count changes.

### Daemon mode (run in the background)

```bash
nohup python pmoves/tools/pr_review_watcher.py \
    --prs 2132,2133,2134 \
    --max-runtime 168h \  # 1 week
    --interval 30 \
    --max-interval 300 \
    --log pmoves/docs/logs/pr_review_arrivals.jsonl \
    --emit-nats \
    > pmoves/docs/logs/pr_review_watcher.out 2>&1 &
```

Check the log for arrivals:
```bash
tail -f pmoves/docs/logs/pr_review_arrivals.jsonl
```

When a review arrives, the log line tells you which PR + which user + which kind of review. Then run the trim cycle for that PR.

### B mode (NATS subscription — when n8n is up)

```bash
python pmoves/tools/pr_review_watcher.py \
    --mode nats \
    --prs 2132,2133,2134 \
    --max-runtime 24h
```

This requires `nats-py` installed AND the n8n webhook bridge up. When B mode is ready, no polling at all — events arrive as NATS messages, same tool processes them.

## Event format

JSONL line per event. Three event kinds:

### `notification` (notifications mode)

```json
{
  "event": "notification",
  "kind": "pullrequest",
  "reason": "review_requested",
  "pr_number": 2132,
  "pr_url": "https://github.com/POWERFULMOVES/PMOVES.AI/pull/2132",
  "title": "A2UI v0.1 + Fordham Hill tenant",
  "updated_at": "2026-07-16T11:35:53Z",
  "unread": true,
  "ts": "2026-07-16T11:35:53Z"
}
```

### `review_state_change` (pr-watch mode)

```json
{
  "event": "review_state_change",
  "pr": 2132,
  "repo": "POWERFULMOVES/PMOVES.AI",
  "ts": "2026-07-16T11:35:53Z",
  "changes": [
    {
      "field": "newReview",
      "author": "coderabbitai",
      "state": "COMMENTED",
      "submittedAt": "2026-07-16T11:35:51Z",
      "body": "## Summary\n\n..."
    }
  ],
  "current": {
    "reviewDecision": null,
    "state": "OPEN",
    "latestReviews_count": 1,
    "comments_count": 1
  }
}
```

### `nats_message` (nats mode)

```json
{
  "event": "nats_message",
  "subject": "github.webhook.review.submitted.v1",
  "data": { ... GitHub webhook payload ... },
  "ts": "2026-07-16T11:35:53Z"
}
```

## Exit codes

| code | meaning |
|---|---|
| `0` | Event detected within `--max-runtime` |
| `1` | Timeout — no event within `--max-runtime` |
| `2` | Error — gh not authed, repo not detected, NATS unreachable, etc. |
| `130` | SIGINT (Ctrl-C) |

## NATS integration

`--emit-nats` publishes each event to `--nats-subject` (default:
`chit.pr.review.detected.v1`). The fallback chain is:

1. `nats pub` CLI
2. `nats-py` (Python NATS client)
3. No-op (silent skip — never blocks the listener)

The outbound subject is what the B-mode `github-pr-review-listener`
service should consume. For A mode, it's a way to broadcast to other
agents on the same NATS cluster.

## Why "no polling"?

The notifications API with ETag is **not polling** in the traditional sense:

| approach | requests/day | latency |
|---|---|---|
| naive `gh pr list` every 60s | 1440 | up to 60s |
| **this tool, notifications mode** (304 most calls) | 0-2 | up to 30s base interval, exponential backoff when 304 |
| webhook (B mode) | 0 | <1s |

The HTTP conditional GET means we make a real call, GitHub tells us "nothing new" instantly (no payload), we sleep. When something arrives, we get the payload in the same call.

## When to upgrade to B mode

When KiloCode finishes the n8n bring-up on the 5090 (per DARKXSIDE 2026-07-16),
the same tool can switch to NATS mode. The CLI doesn't change:

```bash
# A mode (today, no public webhook URL)
python pmoves/tools/pr_review_watcher.py --mode notifications

# B mode (after n8n is up)
python pmoves/tools/pr_review_watcher.py --mode nats
```

The only change is `--mode`. The `--prs`, `--max-runtime`, `--log`, `--emit-nats` flags all stay the same.

## See also

- `pmoves/docs/operations/REVIEW_STYLE_2026-07-15.md` — the meta-doc this tool feeds
- `pmoves/docs/templates/PR_LEARNINGS.template.md` — the bucket template
- `pmoves/tools/pr_hedge_trim.py` — the trim agent (called after the watcher detects an event)
- `pmoves/tools/pr_monitor.py` — the monitor (read-only PR state snapshot)
- `pmoves/n8n/flows/github_webhook_processor.json` — the n8n flow (B mode source)
- `pmoves/services/github-pr-review-listener/` — to-be-created (B mode consumer)
