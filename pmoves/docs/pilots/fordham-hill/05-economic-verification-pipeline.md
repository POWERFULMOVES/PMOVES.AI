# Fordham Hill — Economic-Input Verification Pipeline (Plan)

> **DRAFT — REQUIRES LEGAL/FINANCIAL REVIEW.** This is an engineering plan for how
> real economic figures become trusted pilot inputs. Given the fraud/mismanagement
> context, the numbers driving the pilot's economics must be **extracted from real
> documents and cross-verified across multiple independent layers** before anyone
> relies on them. No figure is trusted because it was typed in.

## Thesis (operator's framing)

Economic inputs **are inputs to Tokenism**, and they **are validated in PMOVES-Wealth**.
The path from a paper bill to a simulation parameter runs through several independent
checks — "multiple ways, multiple layers of verification" — so a wrong or tampered
figure is caught, not propagated.

```
Source documents ──► [L1] extract (≥2 engines) ──► [L2] cross-engine reconcile
   (Verizon bills,        Docling · LangExtract       (agreement score, flag
    co-op financials,      · Tesseract/regex)          mismatches)  ◄── BUILD
    hosting invoices)                                        │
                                                             ▼
        [L5] human review ◄── [L4] ledger validation ◄── [L3] provenance
        (Committee/treasurer,   (PMOVES-Wealth double-      (DoX Evidence →
         reconcile vs totals)    entry + reconciliation)     page/bbox, click-back)
                                                             │
                                                             ▼
                                    [L6] Tokenism inputs (fordham-mesh.json)
                                         flask_params + CHIT mesh_hosting attribution
```

## The layers — grounded in the actual repo

### L1 — Extraction (≥2 independent engines)
- **Docling structural** (tables/text): `PMOVES-DoX/backend/app/ingestion/pdf_processor.py:13-113`; gate `PDF_OCR_ENABLED` + `PDF_FINANCIAL_ANALYSIS`. Table classifier: `financial_statement_detector.py:8-172` (returns a keyword-match confidence — corporate-statement vocabulary, **not** bill-shaped yet).
- **LangExtract LLM few-shot** (independent mechanism): `PMOVES-DoX/backend/app/extraction/langextract_adapter.py:32-80` — Google `langextract` lib, `gemini-2.5-flash` or `ollama:<model>`, returns `{extraction_class, extraction_text, attributes}`. This is the engine that can produce `{vendor, amount, due_date, line_items}` from a prompt + few-shot examples.
- **Fallback signals**: PyMuPDF + `TesseractBlobParser` cascade (`PMOVES-Agent-Zero/helpers/document_query.py:683-712`), regex `BusinessMetricExtractor` (`metric_extractor.py:9-53`), spaCy NER MONEY/ORG (`ner_processor.py`).
- **Prior art**: DoX already has a financial-institution deployment (`PMOVES-DoX/.env.unfcu.example`, `docker-compose.unfcu.yml`) — reuse, don't reinvent.

### L2 — Cross-engine reconciliation  ⚠️ **DOES NOT EXIST — BUILD**
Nothing today diffs Docling-table `amount` vs LangExtract `amount` vs regex `amount`,
computes an agreement score, or flags disagreement. This is the core verification gate
and is net-new (small, deterministic — "tool can tool"): `agree if ≥2 engines match
within tolerance; else flag for human review.`

### L3 — Provenance (exists)
DoX `Artifact → Evidence → Fact` with **page number + bounding-box coordinates**
(`PMOVES-DoX/backend/app/database.py:63-71`) → every figure clicks back to the exact
source region in `FactsViewer.tsx` for a human to eyeball. This is the real
human-in-the-loop substrate.

### L4 — Ledger validation in PMOVES-Wealth (double-entry = the guarantee)
- Load via `POST /api/v1/transactions` (`PMOVES-Wealth/routes/api.php:589`, payload
  `app/Api/V1/Requests/Models/Transaction/StoreRequest.php:60-307`). **No bulk CSV
  importer is vendored** — one API call per transaction group.
- **Structural validation is automatic**: every transaction is two legs summing to zero
  (`TransactionFactory.php:56-83`); the source→destination account-type matrix
  (`config/firefly.php:738-775`, keyed by `AccountTypeEnum.php:31-44`) rejects malformed
  pairings. A non-balancing or wrong-type figure **cannot persist**.
- **Reconciliation** against a stated statement total: `ReconcileController.php` +
  `ReconciliationValidation.php` — the "does calculated balance match the bank statement"
  pass. This is what catches figures that are individually valid but don't sum right.
- **Model**: one `UserGroup` = the co-op ledger (`app/Models/UserGroup.php:36-202`);
  contributions = `deposit` (member Revenue → coop Asset); shared hosting = `withdrawal`
  (coop Asset → Expense, tagged to a "Shared Infrastructure" Budget); per-home savings =
  `PiggyBank` / `transfer`. Traceability: stamp each row's `external_id`/`tags`
  (`tags:["dox:<artifact-id>"]`) + attach the scanned doc (`UserGroup.attachments()`).

### L5 — Human review (Committee on Elders / treasurer)
Double-entry catches *structural* errors, **not** a `$450 → $45` transcription error
against a valid account. That class needs L2's cross-engine flag + L4 reconciliation +
a human confirming against known totals. This is the last, essential layer.

### L6 — Tokenism inputs (validated figures → simulation)
- The sim is **`PMOVES-ToKenism-Multi/flask_backend.py`** (household economics) + a TS
  contracts/CHIT engine under `integrations/contracts/` — there is **no
  `simulation_engine.py`** and **no `fordham-mesh.json`** (author it fresh).
- Map validated figures: door count → `NUM_MEMBERS` (`flask_backend.py:73`); per-home
  premium → `weeklyRevenuePerParticipant` ($35/4.33 ≈ $8.08/wk) or a household budget
  line; KVM hosting → `WEEKLY_COOP_FEE_B` (`flask_backend.py:90`, currently a flat $1/wk
  fee — repurpose, validate against real cost); pooled savings →
  `GROUP_BUY_SAVINGS_PERCENT`. Run: `POST /run_simulation` (`flask_backend.py:825`).
- **Contribution → tokens** is the CHIT Dirichlet engine: `ShapeAttribution.recordAction(
  address, 'group_contribution', amount, week, 'mesh_hosting')`
  (`integrations/contracts/chit/shape-attribution.ts:244-297`) →
  `DirichletWeights.getExpectedAttribution()` (`dirichlet-weights.ts:117-139`) gives
  normalized shares that sum to 1. ⚠️ **BUILD**: no `mesh_hosting` action type exists,
  and nothing multiplies attribution shares × a GroToken reward pool yet.

## What exists vs. what must be built (honest ledger)

| Layer | Exists | Must build |
|-------|--------|-----------|
| L1 extract | Docling, LangExtract, Tesseract, regex, NER | bill/invoice extraction schema (not just corporate statements) |
| L2 reconcile | — | **cross-engine agreement gate** (the core) |
| L3 provenance | Evidence→page/bbox click-back | "flag for review" queue/state |
| L4 ledger | double-entry + account-type matrix + reconcile workflow | DoX→Firefly auto-load + source-tag linkage (no importer vendored) |
| L5 human | provenance viewer | approve/reject reconciliation UI |
| L6 Tokenism | flask sim + CHIT Dirichlet attribution | mesh economic fields, `fordham-mesh.json`, `mesh_hosting` action, share×pool mint |

## Test & validation strategy (the "plan to test/validate")

1. **Golden set** — a handful of *real* Fordham documents (a Verizon bill, a co-op
   financial statement, a Hostinger invoice) with hand-verified ground-truth figures.
   Pipeline must reproduce the known figures. Store as fixtures.
2. **Cross-engine catch test (L2)** — corrupt one engine's output; assert the
   reconciliation gate flags the disagreement instead of silently passing.
3. **Double-entry catch test (L4)** — POST a deliberately unbalanced / wrong-account-type
   transaction; assert Firefly rejects it (`config/firefly.php` matrix).
4. **Reconciliation catch test (L4)** — load line items that don't sum to the statement
   total; assert the reconcile pass flags it.
5. **Semantic-error test (L5)** — inject a `$450→$45` transcription that is structurally
   valid; assert it is caught by cross-engine + reconciliation + surfaced for human review
   (this is the error double-entry alone cannot catch — proves the layers are necessary).
6. **End-to-end** — real bill → extracted → cross-verified → loaded to Wealth →
   reconciled → emitted as `fordham-mesh.json` → sim runs and produces plausible output.
7. **Determinism** — same documents twice → identical figures + identical tally
   (tool-can-tool; no model in the counting path).

## Sequencing (per operator)

1. **First:** finish the SLATE/Starlink A/B + real data gathering (door count, Verizon
   base-vs-premium pricing, KVM hosting cost) — those become the golden-set inputs.
2. **Then:** build L2 (cross-engine reconcile) + the bill schema + DoX→Wealth linkage,
   run the test strategy above.
3. **Then:** author `fordham-mesh.json` from validated Wealth figures, wire the
   `mesh_hosting` CHIT attribution, run the Tokenism sim.
4. **Mullvad L4** activation happens after the A/B + data gathering (deferred).

## Citations

DoX: `pdf_processor.py`, `langextract_adapter.py`, `financial_statement_detector.py`, `database.py`, `.env.unfcu.example`.
Wealth: `routes/api.php:589`, `StoreRequest.php`, `TransactionFactory.php:56-83`, `config/firefly.php:738-775`, `AccountTypeEnum.php`, `ReconcileController.php`, `UserGroup.php`.
Tokenism: `flask_backend.py:72-192`, `integrations/contracts/chit/dirichlet-weights.ts:67-139`, `shape-attribution.ts:244-297`, `grotoken-model.ts`, `API_REFERENCE.md`.
