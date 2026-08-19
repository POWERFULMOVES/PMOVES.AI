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

**Status: wired (since PR #2612 / this slice).** The static half runs on every PR via `.github/workflows/provider-verifier.yml`; the full conformance run is the operator's manual step (see below).

### The static half (PR-time, no API calls)

The workflow `verifier-gate` runs `py pmoves/tools/provider_verifier_gate.py --json` on every PR that touches the relevant paths. It performs 6 checks (no API calls, no secrets):

| Check | Catches |
|-------|---------|
| `verifier_submodule_present` | The submodule is initialized (catches a fresh clone with `--recurse-submodules=false`) |
| `provider_config_well_formed` | `provider.json.example` parses as a JSON array |
| `provider_entries_have_required_fields` | Every entry has `name`, `model`, `base_url`, `api_key` (catches a typo that breaks verify.py's CLI) |
| `example_keys_are_placeholders` | No real API key accidentally committed to the example file (catches a secret leak at PR time, not audit time) |
| `sample_jsonl_present` | `sample.jsonl` is non-empty (required positional arg for verify.py) |
| `verifier_entry_point_importable` | `verify.py` parses cleanly (catches missing deps + syntax errors in the submodule) |

The verdict is posted to the step summary + as a PR comment on FAIL. A FAIL blocks merge (the status check name `verifier-gate` is the load-bearing reference; add it to the required checks list in branch protection if not already there).

The static half is **not** the full conformance check — it can't tell you whether a provider actually behaves like MiniMax. It catches the most common drift: a config error that would break the operator's manual run before the run even starts.

### The full conformance run (operator's manual step)

`verify.py` REQUIRES real API calls (--api-key, --base-url, --model), so it cannot run in CI without exposing secrets, which the F-07 supply-chain note explicitly forbids. The operator runs the full conformance check on the operator's local node, where the API keys live in `pmoves/env.shared` (synced via the secrets-funnel pipeline, never in a workflow file).

```bash
cd Pmoves-MiniMax-Provider-Verifier
python verify.py --providers <your-provider.json> --output-dir /tmp/verifier-run
# Read /tmp/verifier-run/<provider>/summary.json — look at `verdict`
```

The workflow's `workflow_dispatch` trigger is wired for the future: when the operator wants a CI-issued conformance report (not a local one), the dispatch path is ready — just supply the API key as a workflow input and the gate runs the static checks + a real call. Until then, the operator's local run is the canonical path.

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
