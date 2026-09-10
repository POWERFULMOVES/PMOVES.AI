# Runtime Reintegration Queue — from the 2026-09-03 full-fleet audit

Grounded per-item: current fork sync state (measured live via GitHub compare API,
2026-09-03), upstream repo refs, and the decision needed before each runtime PR.

CHIT is the fleet memory: every item below, when landed, signs its trail entry
(`PYTHONPATH=. python pmoves/tools/sign_trail.py --agent-id hermes-agent …`) and
the register row carries the lane. Nothing here is done until it's CHIT-signed.

## 1. wger — restore integrations-* target layer
- Fork: `Pmoves-Health-wger` @ PMOVES.AI-Edition-Hardened — **diverged: 285 PMOVES commits ahead, 14 behind** upstream wger-project/wger:master (`65a1d405`). Upstream drift is small; a local merge-upstream-then-merge-forward is low-risk.
- Runtime need: 6 dead `integrations-*` make targets the runbook relied on. Either restore the target layer (`integrations-up-wger`, `integrations-up-all`, `integrations-down`, `up-external-wger`, `wger-brand-defaults`, `integrations-import-flows`) or finish porting the doc to `up-external` / `brand-defaults` / `n8n-import-flows` (docs already updated in PR #2907; the runtime choice is which layer is canonical).
- Image registry doc'd as cataclysm-studios-inc → compose default is powerfulmoves (fixed in docs; runtime uses compose default).

## 2. firefly-iii — wrap seed script in make targets
- Script exists (`pmoves/scripts/firefly_seed_sample.py`, fixtures + n8n flows present); only the `firefly-seed-sample` / `smoke-firefly` targets are missing.
- Runtime PR: add `firefly-seed-sample` (DRY_RUN passthrough) + `smoke-firefly` wrapping the script; docs already point at direct invocation (#2907) — flip them back to targets once landed.
- Fork: in-tree service (no upstream fork to sync).

## 3. jellyfin external — publish port or finalize doc
- Fork: `PMOVES-Jellyfin` @ Hardened — **diverged: 700 ahead, 9 behind** jellyfin/jellyfin:master (`1ccec11b`). Upstream moves fast; behind-count small but the fork carries the PMOVES image patches.
- Decision: `jellyfin-ext` in external.yml publishes NO ports (host-mount media access only). If fleet access to the UI is wanted, publish `${JELLYFIN_HTTP_PORT:-9096}`; else the doc stands corrected (done #2907).
- `jellyfin-folders` helper: restore as target wrapping `docker exec pmoves-jellyfin jellyfin folders sync` (doc'd that way now).

## 4. hi-rag-gateway v1→v2 — collapse + skill coverage
- Fork: `PMOVES-HiRAG` @ Hardened — standalone (no GitHub parent), last push 2026-03-02; upstream relationship is manual (compare API 404s — the fork predates the parent link or upstream moved).
- Runtime: v1 + v2 service dirs coexist; canonical compose entries unprofiled always-on. Collapse path: keep v2 canonical, profile-gate v1 behind `legacy` (or delete after skill coverage lands).
- Skill: `pmoves-hirag` (retrieval backbone ops: ports 8086/8187 GPU variant, HiRAG submodule layout) — covers the audit's "no skill despite being retrieval backbone" gap.

## Per-node agent topology (corrected 2026-09-03, operator)
- GPU nodes: z890, 5090 (Windows workstations). **spark OFFLINE** — bulk-execution seat vacant until it returns.
- 3 Jetsons (nano-cataclysm, nano-pmoves, nano-1): OTHER GPU nodes — **not linear-prosodic lanes**; treat as edge/runtime seats, no builder.
- b850: services host (currently down); builder moves OFF it per Cole-pattern (canonical builder → KVM VPS #1).
- a2a call path (in-tree already): Hermes/delegate → a2a MCP (`services/agent-zero/python/features/a2a/server.py`) → per-node runtime → CHIT-signed output.
- Sequencing: (1) merge upstream archon dev (IN PROGRESS — `sync/upstream-v0.10` branch, 14 conflicts under reconciliation), (2) builder instance lands on KVM VPS #1, (3) first dsh agent = wrap `archon-fix-github-issue` with `inputs:`/`returns:` signature as a2a tool schema, (4) A0 promoted node-by-node gated on PR #2905 smoke targets.
