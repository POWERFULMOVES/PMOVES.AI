# ORGSIM-MIRROR: Runbook Drift Audit — Have We Done It Yet?

**Date**: 2026-10-13/14 · **Lane**: RUNBOOK DRIFT AUDIT (claimed 2026-10-14T03:35Z, sidecar tree) · **Zero LLM used in the audit itself**

## The mirror

Aragon's orgsim-model-refiner learns an ERP by probing it read-only, keeps sealed hash-chained rulebooks, can say UNDECIDED, and fixed its own scorer (v0.8→v0.9) without re-crediting old scores. We ran the same pattern on our own corpus: **our plans/* runbooks are the rulebooks; reality is the oracle; the auditor is deterministic** — stdlib Python + make -n + curl GET, no AI model calls anywhere in the loop.

- **A-side (rulebook)**: checkable claims extracted from 19 docs in plans/ — 202 claims (167 file paths, 22 endpoints, 13 make targets)
- **B-side (oracle)**: read-only probes — file existence (repo + pmoves/ bases, then tree-wide find), `make -C pmoves -n` dry-run resolution, curl GET with 6s timeout
- **Verdicts**: VERIFIED / DRIFTED / UNDECIDED — fail-closed: unreachable net = UNDECIDED, not dead; ambiguous basename = UNDECIDED, not drifted
- **Sealing**: per-record sha256 hash chain; v2 run digest `898ef4b2fcbafd6…` (tip of chain)

## The A/B eval — and the scorer story (the best part)

| | v1 (deprecated scorer) | v2 (canonical probes) |
|---|---|---|
| Claims | 205 | 202 (noise words dropped) |
| VERIFIED | 107 | **117** |
| DRIFTED | 88 | **24** |
| UNDECIDED | 10 | **61** |

v1 ran bare `make` from repo root — the exact Known-Road trap AGENTS.md documents (targets live in pmoves/Makefile + mk/*.mk includes; secrets-funnel was duplicated twice by agents who skipped this check). It also called "found-elsewhere" paths DRIFTED when that's not decidable by probe. **64 of v1's confident DRIFTED calls were the auditor's own drift.** v1→v2 migrations: DRIFTED→VERIFIED ×10, DRIFTED→UNDECIDED ×51. v1 report preserved as `research/runbook_drift_report_v1_deprecated.json` — Aragon's own move: fix the scorer, keep the old artifact on record, never rerun-credit the old numbers.

**The meta-answer to 'have we done it yet': the drift-hunter needed its own v2 before it could see straight.** Our runbooks drifted AND the first measurement instrument over-confidently mislabeled reality. That's the orgsim lesson running on the mirror.

## What v2 found (24 DRIFTED, classified)

### Real drift — fix the doc
1. `pmoves/config/model_registry.yaml` in LOCAL_REVIEW_INFRA_PLAN_2026-10-12.md — real file is **models.yaml** (verified by ls). One-word bug; would 404 every agent following the plan literally.
2. Make targets `secrets-rotate`, `up-cipher` referenced in HYPERAGINTZ_ORCHESTRATION_SCOPE_2026-09-19.md — no such targets in pmoves/Makefile(+mk includes).
3. `pmoves/docs/operations/AUTH_FLIPON_RUNBOOK_20…` referenced in TAILSCALE_ACL_5090_TIGHTEN_DRAFT — not found in tree (phantom doc reference, the AGInTZ 'phantom cross-PR paths' pattern).
4. Launcher plan cites A0-framework paths (run_ui.py, helpers/server_startup.py, helpers/runtime.py, docs/guides/launcher.md) not in this tree — **auditor limitation noted**: those live in the A0 framework tree, not the PMOVES monorepo; the plan is written for a different root.

### Custody-lifecycle drift (correct by policy)
5. `nats-rotation-elder-melchor-2026-10-11.signed` ×2 — deliberately destroyed in the 2026-10-12 rotation (pre-consumption, per 15:35Z release row). Runbook still references the dead artifact path. Doc should say "superseded 10-12".
   **CORRECTION (00:07Z fold-back pass):** re-read of CREDENTIAL_ROTATION_RUNBOOK L80/L88 shows the doc ALREADY documents the destruction + supersession correctly (L88: 'destroyed... supersession clean'). The flagged lines are a past-tense exposure record, not a live claim — extractor can't yet distinguish history from claim. Auditor limitation, doc was right. No edit made. This is exactly the v0.9 lesson: log the scorer's misses in the open.

### Draft-intent, not drift
6. `openclaw.json` ×7 across KILOCLAW/BROWSER_FLEET/PROVIDER_MIRROR — DRAFT plans describing *planned unbuilt* artifacts. Extractor can't tell intent from claim. Class labeled, not deleted.
7. `.kilocode/chit_signals.yaml` (KILOCODE_PMOVES_INTEGRATION_PLAN) — same draft-intent class.
8. `pmoves-agent-zero/agent.json` / `agent-zero/agent.json` (ACP_REGISTRY draft, HYPERAGINTZ) — planned artifacts.

### Live finding (not drift — an oracle reading)
9. `https://pmoves-spark.tailcad9b4.ts.net/ollama` → **HTTP 502 right now**. Spark ollama surface answering but backend down (roster mismatch known from 16:55Z note). Live monitoring candidate.
10. `http://localhost:8093/geometry/state`, `:8080`, `:8081`, `:11434`, `:5080`… all UNDECIDED (not reachable from sidecar container context) — fail-closed, not asserted dead.

## Have we done it yet? — the answer

**Partially — and now measurably so.** Runbooks drifted (24 confirmed / 202), the corpus-wide pattern matches the AGInTZ harvest (phantom paths, generated-citation rot, draft-vs-reality blur), and the first drift-hunter itself needed a scorer fix — meaning honest eval requires versioned scorers, preserved deprecated runs, and UNDECIDED as a first-class verdict. We have now done what Aragon does: probe read-only, fail closed, seal the record, fix the scorer in the open.

## Next moves (candidate lanes, not claimed)
- Fix the 4 real-drift docs (one-word + target-name + phantom-ref edits)
- Run the auditor on docs/ + AGENTS corpus (scope extension), add intent-classifier for DRAFT vs RUNBOOK docs
- Wire the report into a scheduled weekly drift check (scheduler task) with CHIT-signed delta reports
- Spark /ollama 502 → local-review lane dependency check

## Artifacts
- Tool: `scripts/runbook_drift.py` (v2, 130 lines, stdlib-only)
- Sealed report: `research/runbook_drift_report.json` (run digest `898ef4b2fcbafd6…`, 202 claims, 19 files)
- Deprecated v1: `research/runbook_drift_report_v1_deprecated.json` (205 claims, over-confident scorer)
- Claim register: RUNBOOK DRIFT AUDIT row 2026-10-14T03:35Z

*Zero LLM calls in the audit loop. Two AI calls total this session: writing this analysis + operator comms.*

agent_signature: ACK::agent0-sidecar::ORGSIM-MIRROR-DRIFT::2026-10-14
