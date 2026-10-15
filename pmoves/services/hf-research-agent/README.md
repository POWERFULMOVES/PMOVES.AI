# hf-research-agent

Subscribes to `hf.model.discovered.v1` (from `hf-agent`), scores each model, and publishes `hf.model.evaluated.v1`. Registry row: `hf_research_agent` (port 8202, `/healthz`).

## Scoring

Criteria 1 to 5 are metadata heuristics (downloads, likes, preferred tags, pipeline tag, local-format compatibility). Criteria 6 and 7 (2026-10-11) read the model's own card through `huggingface_hub`, the same surface the `hugging-face-evaluation` skill uses:

| # | Evidence | Points |
|---|---|---|
| 6 | `model-index` evaluation results on the card (`ModelCard.data.eval_results`), attached to the envelope as `eval_results` (first 20, numeric values only) | +15 |
| 7 | A declared `license` on the card | +5 |

`gated`, `library_name` and `base_model` are recorded on the envelope, never scored. `max_score` is 130. `HF_MIN_SCORE` (default 50) is an absolute threshold.

Card evidence is fetched off the event loop with a timeout (`HF_CARD_EVIDENCE_TIMEOUT`, default 20 s). `HF_CARD_EVIDENCE=0` turns it off; the envelope then carries `card_evidence.available: false` and criteria 6 and 7 score nothing. A card fetch that fails is recorded under `card_evidence.errors`, never raised.

## Evaluation job recipe

A model that passes carries `eval_job_recipe`: the `hf jobs uv run` command (from the `hugging-face-jobs` / `hugging-face-evaluation` skills) that would run a real benchmark on HF Jobs. It is a string, not an action: nothing here submits a job or spends compute. `HF_EVAL_FLAVOR` (default `cpu-basic`) and `HF_EVAL_TASK` (default `mmlu`) shape the recipe.

## Env

| Var | Default | Meaning |
|---|---|---|
| `NATS_URL` | `nats://nats:4222` | bus (compose injects the credentialed URL) |
| `HF_TOKEN` | unset | read via `_load_secret`; optional (public cards need none) |
| `HF_MIN_DOWNLOADS` / `HF_MIN_LIKES` / `HF_MIN_SCORE` | 100 / 10 / 50 | thresholds |
| `HF_PREFERRED_TAGS` / `HF_AVOID_TAGS` | empty | comma lists |
| `HF_CARD_EVIDENCE` | `1` | fetch card evidence (criteria 6, 7) |
| `HF_CARD_EVIDENCE_TIMEOUT` | `20` | seconds per model; passed to `model_info` as its request timeout (the card read honours `HF_HUB_ETAG_TIMEOUT` / `HF_HUB_DOWNLOAD_TIMEOUT`, 10 s each), so it bounds the work, not only the wait |
| `HF_CARD_EVIDENCE_WORKERS` | `4` | card reads in flight at once (bounded pool; a burst of slow models queues instead of stacking threads) |
| `HF_EVAL_FLAVOR` / `HF_EVAL_TASK` | `cpu-basic` / `mmlu` | recipe only |

## Tests

`pmoves/tests/test_hf_card_evidence.py` covers the card parser, the scoring deltas, and the recipe string without network.
