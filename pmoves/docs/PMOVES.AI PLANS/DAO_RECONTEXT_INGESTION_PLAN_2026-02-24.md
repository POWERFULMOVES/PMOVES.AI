# DAO Recontext and Ingestion Plan (Hardened)
_Last updated: 2026-02-24_

## Purpose
Create one hardened-ready path to ingest and normalize the new `CATACLYSM_STUDIOS_INC/PMOVES DAO` corpus without mixing speculative research, operational plans, and production assumptions.

This plan aligns to current sprint priorities (`M2 - Creator and Publishing`) while unblocking production-audit closure and DAO/tokenism analysis work.

## Scope
- Recontextualize DAO research into operator-safe PMOVES planning artifacts.
- Normalize competing financial projections into one scenario envelope.
- Define a concrete comparison lane for `shape attribution` vs `predictive markets`.
- Feed the output into PMOVES ingestion channels (Discord drop, Open Notebook, CHIT/Geometry Bus).

## Source Corpus Map
The following inputs were reviewed during this pass:

| Source | Role | Notes |
| --- | --- | --- |
| `CATACLYSM_STUDIOS_INC/PMOVES DAO/Financial Models/PMOVES-5-Year-Financial-Model.md` | Primary PMOVES financial model | Enterprise/community blended model with Year-5 revenue target of `45.2M`. |
| `CATACLYSM_STUDIOS_INC/PMOVES DAO/Research ip theory eco/5-Year Business Projections_ AI - Tokenomics Model/5-Year Business Projections_ AI - Tokenomics Model.md` | External research benchmark | Small business tokenomics comparables with much smaller unit economics. |
| `CATACLYSM_STUDIOS_INC/L4-PLATFORM/projections/5-Year Business Projections_ AI + Tokenomics Model.md` | Existing tracked projections doc | Mirrors the benchmark model; should not be interpreted as PMOVES enterprise forecast. |
| `CATACLYSM_STUDIOS_INC/PMOVES DAO/chats and perplexity/pmoves-strat.md` | Strategy discussion capture | Contains direction and launch framing; requires extraction into explicit action items. |
| `CATACLYSM_STUDIOS_INC/PMOVES DAO/chats and perplexity/pmoves-papers.md` | Research index seed | Pointer to theory papers and CHIT/math framing docs. |

## Contradiction Matrix

| Topic | Conflict | Resolution Rule |
| --- | --- | --- |
| Year-5 revenue | `45.2M` PMOVES model vs `94,277` benchmark model | Treat benchmark docs as comparables, not PMOVES forecast source-of-truth. |
| Valuation | PMOVES model includes `226M` (5x revenue) while benchmark docs are ROI-only | Use valuation only from PMOVES-native model until audited alternative is approved. |
| Token economics maturity | PMOVES model assumes treasury revenue in Years 3-5; benchmark warns on high token failure rates | Keep token revenue as sensitivity band, not base-case certainty. |
| Citation quality | Benchmark doc contains mixed source quality and secondary links | Require source tiering before any projection is promoted to investor/operator docs. |

## Normalized Financial Envelope (Working)
This envelope is the only forecast frame allowed in hardened planning docs until the next audit pass.

| Scenario | Year-5 Revenue | Year-5 Token/Treasury Share | Usage |
| --- | --- | --- | --- |
| Conservative (Ops Floor) | `8M-15M` | `0%-5%` | Production capacity planning, staffing floor, runway protection. |
| Base (Execution Target) | `20M-45M` | `3%-8%` | Default roadmap and partner planning. |
| Expansion (Network Upside) | `45M-80M` | `5%-15%` | Investor narrative and long-range scaling, gated by adoption evidence. |

Rules:
1. Never mix scenario rows in one dashboard figure.
2. Any claim outside these bands must include explicit derivation and reviewer sign-off.
3. Token-derived upside never backfills core operating runway assumptions.

## Shape Attribution vs Predictive Markets (Evaluation Track)

### Working hypothesis
`Shape attribution` is a better fit for PMOVES than generic predictive markets because PMOVES needs explainable behavior adaptation and operator controls, not speculation-first price discovery.

### Decision criteria
- Attribution quality: can we map outcomes to user/agent/model contributions deterministically?
- Compliance burden: does the mechanism introduce avoidable financial-regulatory exposure?
- Operator utility: does it improve routing, model selection, and intervention loops in production?
- Gameability resistance: can bad actors cheaply manipulate outcomes?

### Experiment design (Phase 1)
- Dataset: creator pipeline + channel monitor intake + discord drops.
- Output A: shape-attribution scores in CHIT packets (`geometry.cgp.v1` metadata extension).
- Output B: simulated market-style confidence score (non-monetary sandbox only).
- Compare: calibration error, actionability for moderation/ingestion, operator trust scores.

Gate to proceed: shape-attribution must beat or match simulated market signal on calibration and operator utility without increasing compliance risk.

## Ingestion and Processing Pipeline

### Stage 1: Intake and catalog
- Ingest DAO docs as labeled corpus (`dao`, `tokenism`, `strategy`, `research`).
- Store canonical metadata (source path, authoring mode, confidence tier, revision date).

### Stage 2: Structuring
- Extract claims, assumptions, and projection points into structured records.
- Link each claim to source evidence and scenario envelope slot.

### Stage 3: Runtime wiring
- Channel Monitor forwards approved drops into ingestion.
- Open Notebook indexes processed records for query/review.
- Geometry Bus receives attribution summaries for cross-agent traversal.

### Stage 4: Operator surfaces
- Production Audit Dashboard shows scenario band in use and unresolved contradictions.
- NEXT_STEPS tracks only unresolved gates, not narrative research content.

## Command Path (Documented Order)
Run this exact sequence for deterministic bring-up before validation:

```bash
docker network create pmoves-net || true
make -C pmoves env-setup
make -C pmoves env-check
make -C pmoves supa-start
make -C pmoves supabase-bootstrap
SUPABASE_RUNTIME=cli make -C pmoves up
make -C pmoves smoke
GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu
make -C pmoves channel-monitor-discord-drop-smoke
```

## Acceptance Criteria
- One active scenario band selected and recorded in `PRODUCTION_AUDIT_DASHBOARD.md`.
- DAO docs tagged and ingestible through channel monitor + notebook pipeline.
- Shape-attribution vs predictive-market comparison plan committed with measurable metrics.
- No production planning doc cites benchmark comparables as PMOVES primary forecast.

## Deferred but required follow-up
- Convert high-value DAO files into tracked docs under `pmoves/docs/` with archival provenance.
- Add schema for `dao_claim` and `dao_projection_scenario` records (Supabase migration proposal).
- Emit `agent.graphiti.signed.v1` from trail updates once publisher path is finalized.
