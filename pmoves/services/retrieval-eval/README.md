# Retrieval Eval Service

The retrieval-eval worker scores hi-RAG responses against curated notebook questions. Syncing notebooks into JSONL lets us run quick smoke checks before large persona or publishing pushes.

## Exporting notebook queries

Use `export_notebooks.py` to flatten synced notebook payloads into JSONL queries:

```bash
python pmoves/services/retrieval-eval/export_notebooks.py \
  --source pmoves/services/retrieval-eval/datasets/source/notebook_sync.sample.json \
  --chunks pmoves/services/retrieval-eval/datasets/source/extract_payload.sample.json \
  --output pmoves/services/retrieval-eval/datasets/notebook_queries.sample.jsonl \
  --strict
```

- `--source` accepts multiple files or directories of sync worker payloads.
- `--chunks` points at the extract-worker exports so we can validate `chunk_id` references.
- `--strict` forces a failure if any gold IDs are missing; omit it to log warnings instead.

See [`datasets/README.md`](datasets/README.md) for additional examples and snapshots.

## Smoke dataset + thresholds

`datasets/notebook_queries.sample.jsonl` is our default smoke test. When run against a fresh stack seeded by `hi-rag-gateway-v2/scripts/seed_local.py`, we expect:

- Mean Reciprocal Rank (MRR@10) ≥ **0.80**
- Normalised Discounted Cumulative Gain (NDCG@10) ≥ **0.85**

These thresholds line up with the Roadmap/NEXT_STEPS action items around wiring retrieval-eval into persona gating (`pmoves/docs/ROADMAP.md`, `pmoves/docs/NEXT_STEPS.md`). Record the latest run, thresholds, and any deviations in `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` as part of that testing flow.

## Smoke command

Run the following to exercise every dataset stored in `datasets/`:

```bash
make retrieval-eval-smoke
```

The target iterates each JSONL and calls `python pmoves/services/retrieval-eval/evaluate.py <dataset> --no-query-details`. Ensure the hi-RAG gateway is healthy and seeded before running the smoke.

## Refresh workflow when notebooks change

1. Trigger the notebook sync worker and download the latest payload snapshots.
2. Pull the associated extract-worker payloads (or call `/ingest` with `record_only=true`) so the exporter can validate chunk IDs.
3. Regenerate the JSONL queries with `export_notebooks.py` (see above) and store them under `datasets/`.
4. Re-run `make retrieval-eval-smoke` to capture the new baseline metrics.
5. Update the Roadmap/NEXT_STEPS checklists if the dataset scope or thresholds shift, and log the run metadata in `SESSION_IMPLEMENTATION_PLAN.md`.

## Geometry Bus (CHIT) Integration

- No direct CHIT endpoints. Operates over retrieval APIs; results can inform downstream constellation creation by other services.
