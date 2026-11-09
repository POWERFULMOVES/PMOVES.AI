# School-Psych Workload → ToKenism Model → Wealth Settlement (view v1, 2026-08-08)

> Origin: the SEAP business plan's unit-economics paragraph was fabricated
> (reconciliation fix #4). Operator's ruling: "4 is why tokenism — we need to
> model and output to PMOVES-Wealth." This view is the model design: the
> School Psychology operations doc becomes the first *modeled* (not asserted)
> service workload, with ledger-grade outputs.

## What gets modeled

A Lead School Psychologist across 3 sites (the refreshed
`PMOVES_School_Psychology_Operations_REFRESHED_2026-08-07.md` workload):

| Workload | PMOVES function | Value channel |
|---|---|---|
| IEP translation + audio explanation | CHIT + voice stack | hours returned + access equity (ELL families served) |
| Meeting transcription + emotion annotation | media-audio | hours returned + consent-quality (documented informed consent) |
| Longitudinal records synthesis | Hi-RAG v2 | hours returned + earlier-intervention proxy |
| Report drafting/flagging | Agent Zero | hours returned |
| Multi-site secure access | Tailscale mesh | commute/context-switch reduction |

## Inputs (every one LABELED)

- **ACTUAL** (measure on this fleet): per-task wall-clock for each pipeline
  (diarize+transcribe an IEP meeting, synthesize an IEP audio, Hi-RAG query
  latency) — captured from live service metrics, not estimated.
- **ASSUMPTION** (cite source, label): baseline manual minutes per task
  (published school-psych workload surveys + operator's domain knowledge),
  psychologist loaded hourly cost (public NYC DOE salary schedules), task
  frequencies per student caseload (IDEA/IEP statutory cadence).
- **SCENARIO KNOBS**: caseload size, 3-site travel pattern, ELL fraction,
  automation adoption ramp (0→80% over school year).

## Model shape (ToKenism scenario)

1. **Time-value engine**: (manual minutes − assisted minutes) × frequency ×
   loaded cost → dollars/month returned, per function.
2. **Service-credit loop**: returned hours priced into ToKenism service
   credits (the FoodUSD/GroToken built canon — NOT the unbuilt trinity);
   models the district/coop paying for PMOVES capacity in credits.
3. **Sensitivity pass**: tornado chart over the ASSUMPTION inputs; the model
   ships with its weakest assumptions ranked, per verified-actuals doctrine.

## Settlement (the part that makes it real)

- Simulator run → `export_sim_to_firefly.ts` → **PMOVES-Wealth (Firefly III)**:
  one budget per function, monthly simulated settlement entries, tagged
  `sim:schoolpsych-v1:<run>`.
- Result: the SEAP plan's economics section can cite a LEDGER with an audit
  trail ("open PMOVES-Wealth, filter the tag") instead of a paragraph of
  invented numbers. That IS the demo: provable accounting as product.

## Known blocker (from reconciliation #14)

The Firefly integration is pre-stage: `export_sim_to_firefly.ts` exists but
the live Firefly service isn't wired in compose (no `firefly` service; Wealth
subjects are target contracts). **Phase 1 of this lane is therefore standing
up PMOVES-Wealth's Firefly III container + running the existing exporter
against it** — which simultaneously retires a "Not wired / aspirational" row
in TOKEN_STRUCTURE_REFRESH §6.

## Deliverables

1. `firefly` service live (Wealth stack) + exporter smoke run.
2. Scenario module in ToKenism with the inputs table above.
3. First settled run + a one-page results view (ON + room inbox).
4. SEAP plan §Financial Projections ¶2 replaced with the ledger citation.
