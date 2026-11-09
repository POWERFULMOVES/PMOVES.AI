# MiniMax Verify — Provider

Run the provider-config half of the MiniMax Provider Verifier for a third-party deployment.

## Arguments

- `$ARGUMENTS` - path to a provider.json (or omit for the static gate only)

## Instructions

1. Static half (no API calls, safe everywhere): `python3 pmoves/tools/provider_verifier_gate.py` — six checks over `Pmoves-MiniMax-Provider-Verifier/provider.json.example`. CI runs this as the `verifier-gate` check; it requires the submodule initialized (`git submodule update --init Pmoves-MiniMax-Provider-Verifier`).
2. Provider-specific half: with a provider.json, follow `Pmoves-MiniMax-Provider-Verifier/README.md` — every entry needs `name`, `model`, `base_url`, `api_key`, and `api_key` values must be placeholders in any file that gets committed.
3. M3 format checks live in `m3_format_check/` (model ID default `MiniMax-M3`; text/image/video/stream suites; `M3_BASE_URL`/`M3_API_KEY`/`M3_MODEL` envs).
4. Report the verdict per check; never invent a pass for a check that could not run.

## Notes

- Full conformance (live API calls) is the operator's canonical run by design — keys never enter workflow files.
