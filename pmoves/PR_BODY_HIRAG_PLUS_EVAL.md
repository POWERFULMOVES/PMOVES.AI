# PR: Hi‑RAG hybrid + Retrieval‑Eval sweeps

## Summary
- Enable Hi‑RAG hybrid search flow (dense + BM25) with routing + fallback aligned to the latest retrieval tuning.
- Expand retrieval-eval sweep harness to cover fresh corpora/settings and capture metrics snapshots for comparison.
- Document verification steps and evidence so reviewers can trace outputs back to the new hybrid pipeline and eval runs.
- Related implementation branches: `feature/hirag-hybrid-search` (hybrid search wiring) and `feature/retrieval-eval-sweep` (eval harness refresh); this PR stitches their changes for review.

## Key Changes
- **Hybrid Search**
  - Wire Hi‑RAG gateway to run dense+BM25 hybrid search, including routing guardrails and rerank toggle notes.
  - Surface configuration notes for CPU/GPU endpoints and rerank behavior when hybrid mode is active.
- **Retrieval‑Eval Sweep**
  - Extend sweep matrix to cover new datasets/prompts and record metrics deltas across providers.
  - Capture evidence pointers for the most recent sweep outputs to aid comparison.
- **Documentation/PR Template**
  - Provide reviewer-facing checklist (what to click/run) and evidence anchors for hybrid search + eval outputs.

## How to Verify
1) **Hybrid search path**
   - Ensure Hi‑RAG CPU/GPU services are up (`curl http://localhost:8086/hirag/admin/stats` and `:8087`).
   - Issue a query through the gateway with hybrid enabled; confirm dense+BM25 blend and rerank flag in the response logs.
2) **Retrieval‑Eval sweep**
   - Run the refreshed sweep script/Make target (`make -C pmoves retrieval-eval-sweep` or equivalent) and confirm new matrix entries complete.
3) **Regression checks**
   - Smoke run: `make -C pmoves smoke`.
   - GPU smoke (optional/when rerank is pinned): `make -C pmoves smoke-gpu`.

## Evidence
- Hybrid search request/response snippets showing dense+BM25 candidates and rerank usage.
- Retrieval‑eval sweep summary table (precision/recall/MRR) for the latest run, plus any notable regressions/improvements.
- Logs or screenshots from `make -C pmoves smoke` (and `smoke-gpu` when run) demonstrating healthy paths.

## Reviewer Notes
- Call out any skipped checks (e.g., GPU smoke) and why.
- Note environment expectations (Hi‑RAG CPU/GPU reachable; reranker model available) before reproducing.
- Include links to sweep artifacts (plots/tables) if stored externally.
