---
name: 4090:sitrep
description: >
  Full situation report for the 4090 laptop node: git status, active worktrees,
  GPU (nvidia-smi), NATS health (port 8222), running containers, and open PRs.
  Output formatted as AGNOTE4482 audit record block. Run before every
  CLAIM/RELEASE in AGNOTE4482PHI.t1.md.
---

# 4090:sitrep — Node Situation Report

Runs the 4090 node health check and outputs a formatted AGNOTE4482 audit
record. Use this before making a CLAIM or RELEASE in `AGNOTE4482PHI.t1.md`.

## Run

```bash
# Full sitrep
bash .claude/scripts/node-sitrep.sh 2>/dev/null || {
  echo "=== 4090 SITREP $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo "--- GIT ---"
  git status --short
  git log --oneline -3
  echo "--- WORKTREES ---"
  git worktree list
  echo "--- GPU ---"
  nvidia-smi --query-gpu=name,memory.used,memory.free --format=csv,noheader 2>/dev/null || echo "GPU: not available"
  echo "--- NATS ---"
  curl -sf http://localhost:8222/healthz && echo "NATS: OK" || echo "NATS: DOWN"
  echo "--- CONTAINERS ---"
  docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | head -20
  echo "--- OPEN PRs ---"
  gh pr list --state open --limit 10 2>/dev/null
}
```

## AGNOTE4482 Output Format

The sitrep produces an audit block suitable for pasting into `AGNOTE4482PHI.t1.md`:

```
## SITREP [4090-claude] 2026-05-18T15:00:00Z

**Node**: pmoves-laptop (4090)
**Branch**: feat/shift-crew-4090-skills
**Worktrees**: 2 active
**GPU**: NVIDIA RTX 4090 — 4096MB used / 20480MB free
**NATS**: OK (localhost:8222)
**Containers**: [list]
**Open PRs**: #1535 feat(w0-pr4), #1536 feat(shift-crew-4090-skills)

<!-- GRAPHITI_MARK: sitrep.4090-claude.2026-05-18T15:00:00Z -->
```

## Quick Health Check (5s)

```bash
# NATS + git only — fastest
curl -sf http://localhost:8222/healthz && echo "NATS OK" || echo "NATS DOWN"
git log --oneline -1
git worktree list | wc -l
```

## CLAIM/RELEASE Workflow

1. Run `4090:sitrep` → paste output block into `AGNOTE4482PHI.t1.md`
2. Add CLAIM entry with task description
3. Do work
4. Run `4090:sitrep` again → paste as verification
5. Add RELEASE entry

## Notes

- Replaces manual "Fastest Health Check" block from `AGNOTE4482_SITREP.md`
- `GRAPHITI_MARK` footer required on all audit records per AGNOTE4482 protocol
- GPU check gracefully skips if nvidia-smi unavailable
- See `node-4090-probe` skill for deeper W0 hardware probe
- See `AGNOTE4482PHI.t1.md` § Active Claim Register for current claims
