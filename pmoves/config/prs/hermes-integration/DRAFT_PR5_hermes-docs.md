# DRAFT PR: docs(hermes-docs): add HERMES integration spec + atomic commits guide

**Branch**: `docs/hermes-integration-spec`
**Base**: `origin/main`
**Commits**: `9b4db7522`
**Status**: DRAFT -- integration spec needs live-gateway validation
**Size**: 6 files, 848 lines

## Scope
- `HERMES_AGENT_INTEGRATION.md`: Full integration spec with 6-tier provider
- `HERMES_ATOMIC_COMMITS.md`: Commit standards, CHIT signing
- AGNOTE updates: canonical pointers, claim register, signoff, sitrep

## Why Draft?
`HERMES_AGENT_INTEGRATION.md` contains **stubs** for:
- Submodule fleet (50+ repos described but none verified live except Health-wger/Wealth)
- Provider credentials (all placeholders)
- Gateway health endpoint (`/api/health`) -- hasn't been started

## Pre-merge Checklist
- [ ] Gateway health endpoint validated (after `hermes gateway start`)
- [ ] NATS bridge test passes (`test-nats-bridge.py` against live NATS)
- [ ] Provider table updated with real subscription tiers
- [ ] AGNOTE4482PHI claim moved to DONE after review
- [ ] Commit standards reviewed by Z890-Claude (atomic commit style match)
