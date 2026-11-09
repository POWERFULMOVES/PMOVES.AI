# MiniMax Verify — Conformance

Guide a full MiniMax conformance run for a provider deployment.

## Arguments

- `$ARGUMENTS` - provider name or provider.json path to conformance-test

## Instructions

1. This is the operator-run half (real API calls). Load the key from the tier env (`MINIMAX_TOKEN_PLAN_API_KEY` / `MINIMAX_API_KEY`) — never from a workflow file.
2. Point the verifier at the deployment under test: `M3_BASE_URL`, `M3_API_KEY`, `M3_MODEL` (default `MiniMax-M3`, case-sensitive), then run `Pmoves-MiniMax-Provider-Verifier/m3_format_check/` per its README (text, image, video, stream suites).
3. The six headline metrics (ToolCalls-Match-Rate and friends) and their thresholds are documented in `pmoves/docs/operations/PROVIDER_VERIFIER_GATE.md`; June-2026 reference numbers for genuine MiniMax-M3 are in the submodule README.
4. Record the per-metric results next to the reference row. A metric that could not run is reported as unmeasured — never as a pass.
5. Findings route: provider-side mismatch -> provider fix; fleet-side (profile/endpoint/model-ID) -> the minimax profile lane.

## Notes

- The static gate (`verifier-gate` check) covers every PR; this command exists for the deployments the static gate cannot see.
