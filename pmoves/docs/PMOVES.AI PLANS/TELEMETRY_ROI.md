# Telemetry & ROI Dashboards

_Last updated: 2025-10-05_

## Overview

Publisher-facing services now expose real-time telemetry so operators can
correlate turnaround, approval latency, engagement, and cost. Two lightweight
HTTP endpoints provide quick snapshots while Supabase rollup tables persist the
event-level detail required for historical dashboards.

| Service | Endpoint | Purpose |
| --- | --- | --- |
| `services/publisher/publisher.py` | `http://<host>:9095/metrics` | Aggregated counts/averages for artifact downloads, Jellyfin refreshes, turnaround, approval latency, engagement, and cost inputs. |
| `services/publisher-discord/main.py` | `http://<host>:<app-port>/metrics` | Discord delivery counters plus the same turnaround/approval telemetry derived from published events. |

Both endpoints return JSON with `telemetry` blocks shaped like:

```json
{
  "turnaround_samples": 12,
  "avg_turnaround_seconds": 5400.25,
  "approval_latency_samples": 12,
  "avg_approval_latency_seconds": 900.5,
  "engagement_totals": {"views": 1800, "ctr": 12.5},
  "cost_totals": {"storage_gb": 6.2, "processing_minutes": 44.0}
}
```

Use the metrics endpoints for smoke tests and runbooks; dashboards should query
Supabase directly to avoid scraping service processes.

## Supabase Rollups

| Table | Source | Description |
| --- | --- | --- |
| `publisher_metrics_rollup` | `services/publisher/publisher.py` | One row per published artifact, keyed by `artifact_uri`, capturing turnaround/approval latency plus engagement and cost payloads forwarded from approvals. |
| `publisher_discord_metrics` | `services/publisher-discord/main.py` | Mirrors publisher telemetry for Discord notifications and adds `webhook_success` + `channel` flags to monitor downstream delivery health. |

Both tables are upserted using `services/common/supabase.py::upsert_row`. Use
`PUBLISHER_METRICS_CONFLICT` and `DISCORD_METRICS_CONFLICT` environment
variables to tune the `ON CONFLICT` keys when running migrations.

## Interpreting ROI Dashboards

1. **Turnaround vs. Approval Latency** – Plot `avg_turnaround_seconds` and
   `avg_approval_latency_seconds` trends. Rising approval latency usually points
   to reviewer bottlenecks; rising turnaround means ingest-to-publish automation
   needs tuning.
2. **Engagement Ratios** – Divide `engagement_totals` (views, CTR, likes) by the
   corresponding `cost_totals` (processing minutes, storage GB, egress). High
   engagement with low cost indicates good ROI; low engagement + high cost flags
   candidates for pruning or repackaging.
3. **Channel Health** – Join `publisher_metrics_rollup` and
   `publisher_discord_metrics` on `artifact_uri` (or slug) to confirm Discord
   notifications land for the same assets that hit Jellyfin. Investigate rows
   where `webhook_success` is false to catch stale credentials or rate limits.
4. **Namespace Drill-down** – Group by `namespace` to understand which creator
   lanes drive the most engagement per unit of spend. Feed these insights into
   the sprint prioritisation matrix.

Document snapshot queries alongside dashboards so the next operator can run
validations quickly (see `docs/NEXT_STEPS.md` for the checklist).

