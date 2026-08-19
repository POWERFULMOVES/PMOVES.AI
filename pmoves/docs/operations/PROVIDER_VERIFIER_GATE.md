# MiniMax Provider-Verifier — conformance gate

**Status:** active | **Owner:** Mavis | **Last review:** 2026-08-18

The [Pmoves-MiniMax-Provider-Verifier](https://github.com/POWERFULMOVES/Pmoves-MiniMax-Provider-Verifier) submodule (53d2d8a0 on main) is the load-bearing test for adding any new provider to the Mavis model cascade. This doc tells you how to run it, how to read its six metrics, and what the gate thresholds are.

## What the gate enforces

A candidate provider must demonstrate that a third-party deployment claiming MiniMax compatibility actually behaves like one. The verifier runs the same evaluation prompt set against the candidate and against the official MiniMax Open Platform (the gold standard), then scores six metrics on a 0–100% scale:

| Metric | What it catches | Pass threshold |
|--------|-----------------|----------------|
| **Query-Success-Rate** | 504s, mid-stream drops, malformed responses | ≥ 99% (official: 100%) |
| **ToolCalls-Match-Rate** | Model decides to call a tool when it should / when it shouldn't | ≥ 95% |
| **ToolCalls-Schema-Accuracy** | Tool-call payload (name, args) matches the declared JSON schema | ≥ 95% |
| **ToolCalls-Trigger-Similarity** | F1 score vs. the official deployment's trigger decisions | ≥ 95% |
| **Error-Only-Reasoning-Rate** | Model emits chain-of-thought then stops without producing the required output (a strong signal of bad top-k) | ≤ 1% |
| **Language-Following-Success-Rate** | Model follows language requirements in minor-language scenarios (top-k sensitive) | ≥ 85% |
| **Scenario-Check-Pass-Rate** | Recalls original parameter order from tool definitions (catches alphabetical key re-sorting) | ≥ 95% |

The full metric catalogue lives in the upstream README; the thresholds above are the Mavis cascade's "block" thresholds. A provider that misses any one of them is rejected; a provider that misses none but is below the official baseline by > 5% on any metric is flagged for review.

## How to run it

The verifier ships as a Python package at `Pmoves-MiniMax-Provider-Verifier/`. The submodule is already initialized in PMOVES.AI; you don't need to re-clone.

### 1. Stage a `provider.json`

The verifier reads a `provider.json` (JSONL of `{name, model, base_url, api_key, extra_body?}` records). The example lives at `Pmoves-MiniMax-Provider-Verifier/provider.json.example`:

```json
[
  {
    "name": "provider1",
    "model": "model-name",
    "base_url": "https://api.example.com/v1",
    "api_key": "your-api-key-here"
  },
  {
    "name": "openrouter-minimax",
    "model": "minimax/minimax-m2",
    "base_url": "https://openrouter.ai/api/v1",
    "api_key": "your-api-key-here",
    "extra_body": {
      "provider": { "only": ["minimax"], "allow_fallbacks": false }
    }
  }
]
```

`extra_body` is for OpenRouter-style providers that need a nested provider routing block. The verifier passes it through unchanged.

### 2. Run `verify.py`

```bash
cd Pmoves-MiniMax-Provider-Verifier
python verify.py --providers ./provider.json --output-dir ./output-dir
```

Or use the batch runner for multiple providers in sequence:

```bash
bash run_batch_sequential.sh ./provider.json ./output-dir
```

`--output-dir` defaults to the bundled `output-dir/`. Each provider's results land in a subdirectory named after the provider.

### 3. Read the results

For each provider, the verifier writes:
- `summary.json` — the six metric scores + a pass/fail per metric + an overall verdict
- `tool_call_logs.jsonl` — every tool-call attempt with the model's intended call, the schema validator's verdict, and the per-case error
- `trigger_comparison.json` — the F1 score against the official deployment, broken down by category

The overall verdict is "PASS" if all six metrics clear the thresholds; "FAIL" if any one misses; "REVIEW" if all pass but the deltas to official are > 5% on any metric.

## Gate in CI

The Mavis model-cascade CI (not yet wired — see "Follow-up" below) will run the verifier on every PR that touches `pmoves/contracts/providers/` or that adds a new entry to the `pmoves_minimax_mcp` provider block. A FAIL verdict blocks merge; a REVIEW verdict requires operator sign-off.

For now, gate manually:

```bash
cd Pmoves-MiniMax-Provider-Verifier
python verify.py --providers <your-provider.json> --output-dir /tmp/verifier-run
# Read /tmp/verifier-run/<provider>/summary.json — look at `verdict`
```

## What you CAN'T skip

The verifier is non-bypassable. Three reasons:
1. **Top-k drift is silent.** A provider that ships a slightly-wrong `top_k` parameter still answers; the answers just gradually shift on the language-following and scenario-check metrics. A manual "looks fine" review misses this.
2. **Key re-sorting is silent.** Some OpenAI-compatible gateways alphabetize JSON object keys in tool definitions. The model still gets a valid schema; it just doesn't recall the original parameter order. The scenario-check metric is the only one that catches it.
3. **Error-only-reasoning is success-coded.** A misconfigured deployment returns HTTP 200 with a chain-of-thought-only payload. The gateway reports success; the application hangs on the missing `content` field. The error-only-reasoning metric is the only one that catches it.

## What this is NOT

- Not a load test. The verifier checks *correctness*, not throughput or concurrency.
- Not a security test. The verifier does not probe for prompt-injection, jailbreaks, or token-leak.
- Not a model-quality test. The verifier checks that the provider *matches the official behavior*, not that the official behavior is good. If the official baseline degrades, the verifier's thresholds stay the same and the gate gets stricter; that's intentional.

## Follow-up

The CI gate is described but not wired. The pattern that fits: extend `.github/workflows/python-tests.yml` (or a new `provider-verifier.yml`) to run `verify.py` against the `provider.json` in `Pmoves-MiniMax-Provider-Verifier/provider.json.example` on every push, with the verdict posted back to the PR as a status check. A FAIL blocks merge. Wiring this is a separate slice — it's not in scope for the wire-up PR because the operator hasn't asked for it, and the verifier submodule is owned by a different team.

## Reference

- Submodule: `Pmoves-MiniMax-Provider-Verifier/` (PMOVES fork of MiniMax-Provider-Verifier; tracks upstream `MiniMax-Provider-Verifier`)
- Submodule pin: `53d2d8a08029169d79ae1a9328574c67779d2768`
- Upstream README: see `Pmoves-MiniMax-Provider-Verifier/README.md`
- Sample run output: `Pmoves-MiniMax-Provider-Verifier/output-dir/`
- Mavis model cascade context: `pmoves/contracts/schemas/pmoves-bootstrap/example.cgp.yaml` → `services.minimax.verifier`
