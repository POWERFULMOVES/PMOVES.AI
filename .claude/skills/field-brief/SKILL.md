---
name: field-brief
description: >
  Template a KiloCode implementation brief at .kilo/command/<name>.md.
  Generates the required sections: ## Arguments, ## Implementation,
  ## Related, ## Notes. Uses Three-Body pattern: Claude analyzes →
  KiloCode (GLM-5.1 on 5090) implements → trail signed on completion.
---

# 4090:field-brief — KiloCode Field Brief Templater

Creates a `.kilo/command/<name>.md` brief that KiloCode (GLM-5.1) on the
5090 node can pick up and implement. Follows the Three-Body delegation
pattern: Claude (4090) writes the analysis spec, KiloCode executes the
implementation, trail is signed on completion.

## Create a Brief

```bash
# Create brief for a new feature
BRIEF_NAME="add-nats-health-check"
cat > ".kilo/command/${BRIEF_NAME}.md" << EOF
# ${BRIEF_NAME}

## Arguments

- `service_name` (string, required): Name of the service to health-check
- `nats_url` (string, optional): NATS URL, default `nats://localhost:4222`
- `subject` (string, optional): Health subject, default `health.<service_name>.v1`

## Implementation

1. Add health check publisher to the target service
2. Subscribe to `health.<service_name>.v1` in the monitoring service
3. Wire into the existing Prometheus metrics exporter

Files to modify:
- `pmoves/services/<service_name>/health.py` — add publisher
- `pmoves/services/monitoring/subscriber.py` — add subscription

## Related

- `pmoves/services/monitoring/` — existing monitoring service
- `pmoves/configs/nats-subjects.md` — NATS subject catalog
- `AGNOTE4482_SITREP.md` — health check reference

## Notes

- Follow existing pattern in `pmoves/services/agent-zero/health.py`
- Publish interval: 30s
- Payload: `{service, status, ts, node}`
EOF
echo "Brief created: .kilo/command/${BRIEF_NAME}.md"
```

## Existing Briefs

| Brief | Status | Purpose |
|-------|--------|---------|
| `.kilo/command/smoke.md` | Reference | Smoke test runner |
| `.kilo/command/sitrep.md` | Reference | Sitrep generation |
| `.kilo/command/beats-to-voice.md` | Active | Shift Crew pipeline |
| `.kilo/command/bpm-encoder.md` | Active | BPM encoding |
| `.kilo/command/cgp-packet.md` | Active | CGP v0.2 packet builder |
| `.kilo/command/geometry-bridge.md` | Active | Geometry bus bridge |

## Three-Body Delegation Pattern

```
Claude (4090-claude)          KiloCode (GLM-5.1 / 5090)
      │                               │
      │─── write .kilo/command/ ──────>│
      │    brief with spec             │
      │                               │─── implement ───>
      │                               │    (blueprint-first)
      │                               │<── commit ───────
      │<── chit:sign-trail ────────────│
      │    (GRAPHITI_MARK footer)      │
```

## Format Requirements (enforced by kilo-brief-check.sh hook)

Every `.kilo/command/*.md` file MUST have:
```
## Arguments
## Implementation
## Related
## Notes
```

The `kilo-brief-check.sh` PostToolUse hook validates this automatically
and warns to stderr if sections are missing.

## Notes

- KiloCode runs GLM-5.1 on the 5090 node (not locally on 4090)
- Always include file paths and function names — KiloCode needs precision
- The `## Implementation` section should be specific enough to implement without questions
- After implementation, run `chit:sign-trail` to close the brief loop
