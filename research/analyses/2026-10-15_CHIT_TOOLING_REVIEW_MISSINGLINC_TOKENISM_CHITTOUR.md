# CHIT Tooling Review — MISSINGLINC · ToKenism · chit-tour

**Date**: 2026-10-15 · **Lane**: CHIT TOOLING REVIEW (claimed 17:50Z, sidecar) · Read-only review; all paths verified on disk this session.

## 1. MISSINGLINC — mint certification & drift posture

**State (verified from reviews/AGINTZ_ACK_AND_NETWORK_MAP_2026-10-12.md + register):**
- PR #2510 MERGED — MiSSinGLinC validator AgentMintSpec, QA-gated Wave-0 ✅
- Support chain all merged: #2751 (node identity binding), #2739 (claude_4090 registration), #3143 (per-agent cipher tokens), #2959 (GitHub App install-token mint), #3070 (Tailscale OAuth mint) ✅
- #3359 OPEN — enrollment serial minting + round-trip tests (merge-wave follow-up, closes the bot's producer/consumer contract finding)

**Gaps:**
1. No scheduled re-verification: the validator ran once at QA gate; nothing re-proves mint integrity as nodes enroll over time.
2. Network-map coverage (~70-75% at 10-12) has no drift check — WiFi Halo quartet still 0% verified.

**Recommendation:** wire MISSINGLINC validation into a scheduled chit_target_drift_check-style gate (the tool exists — `pmoves/tools/chit_target_drift_check.py` pattern: 'does each target name the secret it's actually for' → same question for mints: 'does each mint still verify against its issuer'). Natural owner: enrollment lane post-#3359.

## 2. ToKenism — simulation mechanics ↔ CHIT

**State (verified from pmoves/config/rooms/tokenism.room.exchange.json + 10-11 analysis):**
- Room manifest real: rehearsal stage, agent 5090-claude / alter 5090-tokenism, public visibility, tokenism-mint theme, simulator-main panel, capabilities `simulate, scenario, calibrate, chit-sign` ✅
- Mechanics mapped from the blockchain explainer (xCAot75ztsg): per-member ledger copies + divergence detection = free Byzantine-fault injector; double-spend replay = the idempotency test a settlement simulator needs.

**Gaps:**
1. `chit-sign` capability is declared in the manifest but **no export path is CHIT-signed** — Firefly III ledger exports are unsigned rows.
2. Operator-stated 50 members / 156 weeks remains UNVERIFIED in repo (flagged 10-11, still true).

**Recommendation:** settlement-ledger export wraps in the sign-trail pattern (HMAC bundle, kid, round-trip verify) — the simulator's `calibrate` step becomes a CHIT verify pass. That makes ToKenism the *audience-facing demo of CHIT itself*: every simulated week settles with a verifiable seal. Symmetry the brand deserves.

## 3. chit-tour — already the living-provenance standard

**State (verified from website/chit-tour/):**
- `data.js` SOURCES map: every UI claim carries its repo path (docs, registry, projections CSVs) — **the 'window to the source' is already built here** ✅
- `pillars-lab.js`: every number computed in-browser with repo parameters; "Where the shipped code differs from the doc prose, the lab says so. No canned charts." ✅ — this is the exact standard the operator wants for playlist provenance.

**Gaps:**
1. `data.generated.js` = crawl snapshot — same rot class as playlist video-count drift (counts quoted anywhere are crawl snapshots; re-verify at use time).
2. **No automated check that SOURCES paths still exist.** The provenance map itself can drift.

**Recommendation (the convergence):** point `scripts/runbook_drift.py` at `website/chit-tour/data.js` — the SOURCES map is literally a corpus of `file_path` claims (one-line glob/extractor extension). The drift auditor auditing the provenance window closes the loop: the tour's citations get the same drift discipline as the runbooks. Proposed as the v3.1 scope candidate, folded into the weekly watch.

## 4. Tooling inventory finding

20+ CHIT tools exist (`chit_verify`, `chit_provenance_check`, `chit_target_drift_check`, `chit_security_validator`, `topology_chit_gate`, `sign_trail`, encode/decode/manifest family…) but **no single index maps question → tool**. Recommendation: one SERVICE_DOCS_MATRIX row — "CHIT tooling: which tool answers which question" — 30 minutes, prevents the next duplicate-funnel-class incident.

## Action summary

| # | Item | Owner-lane | Size |
|---|---|---|---|
| 1 | MISSINGLINC scheduled re-verify gate | enrollment (post-#3359) | M |
| 2 | ToKenism export → CHIT-signed bundles | 5090 tokenism alter | M |
| 3 | drift-audit chit-tour SOURCES map | sidecar (v3.1 + weekly) | S |
| 4 | CHIT tooling index (question→tool) | sidecar docs lane | S |
| 5 | #3359 review/merge follow-through | merge wave | existing |
