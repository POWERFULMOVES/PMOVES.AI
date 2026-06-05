# DRAFT PR: feat(hermes-profile): add elder-melchor + 7-node fleet profiles

**Branch**: `feat/hermes-profiles-elder-melchor`
**Base**: `origin/main` (36926493)
**Commits**: `1b0f1f593`...
**Status**: DRAFT -- awaiting SPARK/B850 real-context validation
**Size**: 15 files, 1,877 lines (target: < 400 lines per PR, split before merge)

## Scope
- Ageless Beauty practice workstation profile (cloud-first, HIPAA placeholder)
- Z890, 5090, 4090, Spark, B850, KVM4-1 fleet profiles
- NATS bridge config for elder-melchor
- Pinokio HERMES mod launcher

## Why Draft?
These profiles were written WITHOUT live hardware scans of SPARK/B850/KVM4-1.
All GPU specs are **stubs** estimated from naming conventions.
We need real hermes `config.yaml` from each node to:
- Verify provider model names (e.g., is Spark's NeMo model `nvidia/nemotron-4-340b` or `nvidia/llama-3.1-nemotron-70b`?)
- Confirm Ollama bindings (CPU-only nodes like KVM4-1 may use `openai-api`)
- Validate tailscale IPs and NATS leaf node config

## Pre-merge Checklist
- [ ] SPARK: hermes `config.yaml` inspected and model field corrected
- [ ] B850 (Knuckles): hermes `config.yaml` inspected, ROCm flags verified
- [ ] 5090: VRAM spec confirmed (24GB or 32GB?)
- [ ] Z890: RTX 3090 Ti spec confirmed by Z890-Claude
- [ ] All profiles YAML-lint valid
- [ ] Split into smaller PRs if > 400 lines (suggested: elder-melchor only + fleet common)

## Related
- AGNOTE4482PHI.t1 claim: HERMES-AGENT (elder-melchor)
- Follow-up: `DRAFT_PR6_hermes-research.md` for context-gathering plan
