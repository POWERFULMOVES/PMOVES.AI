# ToKenism Business-Idea Demo — sim → PMOVES-Wealth Export Wiring (Design Spec)

**Author:** 5090-CLAUDE (Fable 5) · 2026-07-11
**Status:** design — grounded by a 4-agent fan-out (branches / wealth-export / tokenism-state / ingest-chain); plan + implementation to follow.
**Operator directive:** "wire demo of that tokenism to pmoves wealth export so user can test business ideas — this will require pmoves.yt, transcribe-and-fetch, youtube monitor and opennotebook."
**Room:** `tokenism.room.exchange` (added public in the rooms-curation PR) — its `wealth-ledger` app ships `status: "planned"` and its `tokenism-export-to-wealth` binding ships `enabled: false`; **this spec is what flips both on.**

---

## Goal (user story)

A user walks into the ToKenism Exchange room with a business idea. They can:
1. (Optionally) seed research: point PMOVES.YT at YouTube material about the idea; transcripts land in the room's Open Notebook workspace (`tokenism-demo` / `business-idea-tests`).
2. Configure a scenario (population, weekly revenue/cost assumptions — the existing `ProjectionModel` / `ScenarioConfig` objects, e.g. `AI_ENHANCED_LOCAL_SERVICE`).
3. Run the simulation in the ToKenism simulator.
4. **Click "Export to Wealth Ledger"** — the sim's representative agents become Firefly III accounts with weekly income/expense journals, browsable in the actual PMOVES-Wealth UI as if the hypothetical business already had a transaction history, and exportable as CSV via Firefly's native `GET /api/v1/data/export/*`.
5. Round-trip: pull *real* spending back through the existing calibration engine to sanity-check the projection's assumptions.

## What already exists (fan-out findings — do not rebuild)

- **The bridge is ~80% built**, CLI-only, in `PMOVES-ToKenism-Multi/integrations/firefly/`:
  `firefly-client.ts` (+ Python twin `pmoves_backend/adapters/firefly.py`), `data-transformer.ts` (Firefly categories → FoodUSD sim categories), `calibration-engine.ts` (real-spend → sim-parameter calibration with confidence scoring), `firefly-integration.ts` (orchestrated compare reports), and **`export_sim_to_firefly.ts`** — sim → Firefly push with `--dry-run` (default-safe) and `--nats` (publishes `tokenism.export.result.v1`).
- **Firefly export API** (native, OAuth2-gated, CSV): `PMOVES-Wealth/routes/api.php:150-169` → `/api/v1/data/export/{accounts,budgets,categories,transactions,…}`.
- **Deploy unit:** `pmoves/compose/docker-compose.firefly.yml` (`firefly` + `firefly-db`, profile `firefly`, `make -C pmoves up-firefly`). Health probe `GET /api/v1/about`.
- **Approval-gated settlement design already written:** `pmoves/docs/TAC/TAC_TOKENISM.md` "Tokenism Firefly settlement" — dry-run default; live writes require signed executor identity + operator approval. This spec inherits that gate wholesale.
- **No unmerged branch work to recover** — a dedicated branch fan-out confirmed every ToKenism branch/PR (#1756, #1931, #1453, #1497, #1939, …) is already on main; `codex/tokenism-return` is stale-archive. G-series work below is **new work**, not a merge.

## Gaps to close

| # | Gap | Shape |
|---|-----|-------|
| **G1** | **HTTP trigger** — the bridge is `npx ts-node` CLI-only; no route a UI can call. | Thin endpoint wrapping the existing exporter (lean: FastAPI sidecar in `PMOVES-ToKenism-Multi/pmoves_backend` calling `import_simulation_results()`, since the Python twin already exists; alternative: Next.js API route shelling the ts exporter). `POST /v1/tokenism/export/wealth {scenario_id, dry_run=true}` → `{summary, report_refs}`; publishes `tokenism.export.result.v1` on completion. **Dry-run is the default and the only mode until the TAC settlement gate is satisfied.** |
| **G2** | **Room UI trigger** — `/demo/wealth` route + button; flip `tokenism.room.exchange` manifest: `wealth-ledger.status → active`, `tokenism-export-to-wealth.enabled → true`. | Lands ONLY with G1 verified end-to-end (manifest honesty rule). |
| **G3** | **Port drift** — TAC_WEALTH + integration dossier say host **8075** is canonical (avoids Agent Zero on 8080); the compose file maps `8080:8080`. | One-line compose fix to `${FIREFLY_HOST_PORT:-8075}:8080` + doc line. Do first; everything downstream points at 8075. |
| **G4** | **Research seeding** — YT → Open Notebook path into the room's workspace (`workspace_ref: tokenism-demo`). | Ingest-chain fan-out confirmed: the pipeline runs discovery (channel-monitor :8097) → PMOVES.YT (:8077) transcription → Supabase `youtube_transcripts` + MinIO → Hi-RAG → NATS `ingest.transcript.ready.v1` automatically, but **nothing forwards transcripts into Open Notebook** (which is HTTP-push-only by design — no NATS consumer). Fix: one small `notebook-yt-bridge` worker copying the proven `NotebookPublisher` pattern from `pmoves/services/deepresearch/worker.py` — subscribe `ingest.transcript.ready.v1`, fetch the transcript text (Supabase row or the event's MinIO `storage.bucket/key` pointer), `POST /api/sources/json` (Bearer `OPEN_NOTEBOOK_API_TOKEN`) into the demo notebook. Static `TOKENISM_NOTEBOOK_ID` env first (matches both existing publishers); per-channel `channel_tags` → notebook routing is a later enhancement. Once transcripts land, ToKenism reads them back via Open Notebook's own `/api/search` / `/api/sources/{id}/insights` — no extra plumbing on the sim side. Scenario-parameter extraction from transcripts stays a later, separate enhancement — not demo-blocking. |
| **G5** | **Subject registration** — `tokenism.export.result.v1` is emitted by the CLI on `--nats`. | Verify it's in `.claude/context/nats-subjects.md` / geometry catalog; register if missing (it is already pre-authorized in the room manifest's publish allow-list). |

## Non-goals / guardrails

- **No live Firefly writes** without the TAC_TOKENISM settlement gate (signed executor identity + operator approval + deployment attestation). The demo is dry-run + demo-instance writes only.
- No real-money integration of any kind; Firefly here is a *ledger visualization* of simulated economies.
- No new simulator features — scenario objects and the calibration engine are consumed as-is.
- Secrets (Firefly OAuth token for the exporter) ride the env.tier → secrets-funnel pipeline; never inline.

## Phasing

- **W1 — plumbing:** G3 port fix → G1 HTTP wrapper (dry-run only) → G5 subject registration. Verifiable by curl: scenario in, dry-run report out, NATS event observed.
- **W2 — the demo moment:** G2 room UI trigger + manifest flip; screenshot-verified in the Exchange room; Firefly demo instance browsable.
- **W3 — research seeding:** G4 YT→Notebook wiring into `tokenism-demo` workspace (depends on ingest-chain report; channel-monitor + transcribe-and-fetch are known-live from the 2026-04 YT pipeline sessions).

Each phase = its own plan → reviewed PR (three-body: delivery=5090, control=DARKXSIDE, memory=AGNOTE trail). W1 is the next plan to write.

## Open questions (for review)

1. **G1 host:** FastAPI sidecar in ToKenism-Multi (Python twin, matches simulator stack) vs Next.js API route (same repo as the demo UI)? Lean: Python sidecar — the adapter with `import_simulation_results()` already lives there and stays UI-agnostic.
2. Which Firefly instance does the demo target — a dedicated throwaway `firefly-demo` service (clean slate per demo run) or the operator's instance in dry-run only? Lean: dedicated demo instance, so "browse the ledger" actually shows data without touching real books.
3. Does the `?agent=`-style room identity (DL-3) select whose scenario library loads in the Exchange room, or is the demo single-tenant for now? Lean: single-tenant demo first.
