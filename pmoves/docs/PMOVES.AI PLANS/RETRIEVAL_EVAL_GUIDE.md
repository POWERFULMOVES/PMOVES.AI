# Retrieval Evaluation Playbook
_Last updated: 2025-02-18_

This guide covers end-to-end retrieval quality evaluation for the hi-RAG stack, including:

- Preparing datasets and optional bias/stress suite definitions.
- Running the baseline `evaluate.py` script and the rerank comparison harness.
- Persisting results as JSON and generating Model Card artifacts under `docs/evals/`.

## Prerequisites

1. **Environment** – Activate the repo Python environment (3.11+) and install dependencies:
   ```bash
   pip install -r pmoves/services/retrieval-eval/requirements.txt
   pip install -r pmoves/services/retrieval-eval/requirements-rerank.txt
   ```
2. **Gateway access** – Export the hi-RAG endpoint used for evaluation:
   ```bash
   export HIRAG_URL=http://localhost:8087  # adjust for your deployment
   ```
3. **Datasets** – JSONL files where each line represents a query definition. Canonical samples live under `pmoves/datasets/retrieval/`; copy or extend them to add your own evaluation packs. Minimum schema:
   ```json
   {
     "query": "Find docs about EvalOps",
     "namespace": "pmoves",                // optional, defaults to "pmoves"
     "relevant": ["chunk-123", "chunk-456"], // or "gold_ids" for rerank evals
     "metadata": {"group": "control"},     // optional, used for suite filters
     "tags": ["bias", "stress"]            // optional helper labels
   }
   ```
   > Tip: include `metadata` or `tags` to enable fine-grained bias/stress slices.

## Bias & Stress Suite Configuration

Suites are defined via JSON to describe subsets of queries and optional thresholds. Example (`suites/bias_stress.json`):

```json
{
  "suites": [
    {
      "name": "gender_balance",
      "type": "bias",
      "description": "Queries tagged female vs male personas",
      "filters": [{"field": "metadata.gender", "in": ["female", "male"]}],
      "metrics": ["mrr", "ndcg"],
      "thresholds": {"mrr": {"min": 0.35}}
    },
    {
      "name": "long_tail_latency",
      "type": "stress",
      "filters": [{"field": "tags", "contains_any": ["long_tail"]}]
    }
  ]
}
```

Filters support dotted paths into the source query (`metadata.gender`) as well as `tags`. Available operators:
- `equals`, `not_equals`
- `in`, `not_in`
- `contains_any` (for array fields)
- `exists` (boolean)

Metrics default to `mrr`/`ndcg` for baseline evals and `recall`/`ndcg` for rerank runs unless overridden.

## Baseline Retrieval Evaluation (`evaluate.py`)

Run the script against a dataset to compute MRR/NDCG and suite breakdowns. Example:

```bash
python pmoves/services/retrieval-eval/evaluate.py \
  pmoves/datasets/retrieval/queries.jsonl \
  --k 10 \
  --suites pmoves/datasets/retrieval/suites/bias_stress.json \
  --output artifacts/retrieval/baseline_results.json \
  --csv --csv-path artifacts/retrieval/baseline_results.csv \
  --label "baseline-m2" \
  --include-hits
```

Key options:
- `--k`: number of hits requested from hi-RAG.
- `--suites`: path to suite JSON (optional).
- `--output`: writes structured JSON (includes dataset hash, suite metadata, per-query details unless `--no-query-details`).
- `--csv`: emit per-query CSV (stdout by default or `--csv-path`).
- `--include-hits`: attach retrieved hit summaries to the JSON payload.

Output JSON structure highlights:
- `overall`: contains `count`, `k`, and a nested `metrics` object with averaged `mrr`/`ndcg` values.
- `per_query`: per-query metrics plus hit relevance flags (omit with `--no-query-details`).
- `suites`: grouped metrics for each bias/stress slice, including threshold pass/fail signals.
- `suite_config`: SHA256 + path metadata for the bias/stress configuration used during the run.

## Rerank Evaluation Harness (`eval_rerank.py`)

Compare baseline vs reranked retrieval for the same dataset:

```bash
python pmoves/services/retrieval-eval/eval_rerank.py \
  --data pmoves/datasets/retrieval/queries_rerank.jsonl \
  --k 20 \
  --suites pmoves/datasets/retrieval/suites/bias_stress.json \
  --output artifacts/retrieval/rerank_results.json \
  --table \
  --label "cohere-v3" \
  --include-hits
```

Important flags:
- `--skip-baseline` / `--skip-rerank`: focus on a single retrieval mode.
- `--table`: render a quick Recall/NDCG summary table in the console.
- `--no-query-details`: suppress per-query payloads while retaining aggregate metrics and suite breakdowns.

The resulting JSON contains:
- `settings`: one entry per evaluated mode (`baseline`, `rerank`) with aggregate metrics and optional per-query details.
- `comparison`: delta between rerank and baseline metrics when both modes are run.
- `suites`: bias/stress aggregates scoped to each mode.

## Generating Model Cards & Eval Packs

After producing one or more JSON results, create a Model Card bundle:

```bash
python pmoves/services/retrieval-eval/generate_model_card.py \
  --model-name "hi-RAG Cohere Rerank" \
  --results artifacts/retrieval/baseline_results.json artifacts/retrieval/rerank_results.json \
  --output-dir docs/evals
```

Artifacts created under `docs/evals/<slug>/<timestamp>/`:
- `model_card.md`: Markdown report summarising datasets, metrics, and suite outcomes.
- `model_card.html`: HTML rendering (falls back to `<pre>` if the `markdown` package is unavailable).
- `summary.json`: Machine-readable bundle covering runs, dataset provenance (including SHA256 hashes), suite configs, comparisons, and optional notes (`--notes path/to/context.json`).

Include these files when publishing evaluation packs or sharing Model Cards with stakeholders.

## Troubleshooting & Tips

- **Timeouts** – adjust `--timeout` (seconds) on either script if the gateway is under heavy load.
- **Suite sanity** – add `--label` to clearly trace runs when aggregating multiple JSON files into a single Model Card.
- **Data drift** – dataset SHA256 hashes in the JSON outputs allow downstream tooling to detect when source queries change.
- **Versioning** – commit generated artifacts (Markdown/HTML/summary JSON) under `docs/evals/` for reproducibility alongside evaluation inputs.
