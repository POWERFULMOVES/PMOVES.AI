# Model — Verify Provider

Run the provider-conformance gates for a model family's deployments.

## Arguments

- `$ARGUMENTS` - family (default `minimax`) and optional provider.json path

## Instructions

1. MiniMax family — the two-piece design:
   - Static (everywhere-safe): `python3 pmoves/tools/provider_verifier_gate.py --json` — six checks, CI's `verifier-gate` check consumes the same output. Requires the submodule: `git submodule update --init Pmoves-MiniMax-Provider-Verifier`.
   - Full conformance (operator-only, real API): `minimax-verify/conformance` command + `m3_format_check/` suites with `M3_BASE_URL`/`M3_API_KEY`/`M3_MODEL`.
2. Other families: route to their owning lane's check (kilocode cascade → `pmoves/tools/models/kilocode_provider_cascade.yaml` sanity + TensorZero function config).
3. Report per-check verdicts; an unrunnable check is `unmeasured`, never `pass`.
4. On mismatch, classify: provider-side (their deployment) vs fleet-side (suit/profile/endpoint drift — fix in `pmoves/configs/model-suits/`).

## Notes

- Keys never enter workflow files; the operator's env is the canonical conformance surface.
