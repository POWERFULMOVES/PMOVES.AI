# DRAFT PR: docs(hermes-research): add Neotron 3 Ultra + Hermes Agent research + submodule init scripts

**Branch**: `docs/hermes-neotron-research`
**Base**: `origin/main`
**Commits**: `1e7f805ab`
**Status**: DRAFT -- research context; submodule scripts untested
**Size**: 11 files, 2,262 lines

## Scope
- `RESEARCH_Neotron3_Ultra.md`: NeMo 72B architecture research
- `RESEARCH_Hermes_Agent_Deep_Dive.md`: v0.15.1 feature analysis
- `init-ageless-beauty-submodules.sh/.bat`: submodule init wrappers

## Why Draft?
Research docs are fine, but submodule scripts are **untested**:
- `Pmoves-Health-wger` and `PMOVES-Wealth` were initialized on elder-melchor but not verified
- Other submodules (n8n, MAI-UI, supabase, Jellyfin) not pulled
- Scripts need `chmod +x` on Linux nodes

## Pre-merge Checklist
- [ ] Submodules verified on elder-melchor (`make -C pmoves submodule-integrity`)
- [ ] Health-wger `docker-compose up` tested
- [ ] Wealth `php artisan` or equivalent smoke test
- [ ] Scripts tested on both Windows (batch) and WSL/Linux (bash)

---

## Cross-Node Context Gathering Plan

### Phase 1: Elder-Melchor (DONE)
- [x] Hermes Agent v0.15.1 installed
- [x] Profile `pmoves-hermes-elder` created
- [x] Config validated (`hermes doctor`)
- [ ] Gateway started (pending secrets)
- [ ] NATS bridge test (pending live NATS)

### Phase 2: SPARK (GB10 128GB) - NEXT
- [ ] SSH/tailscale to spark
- [ ] Install Hermes Agent (`uv pip install hermes-agent` or `pip install`)
- [ ] Create profile `pmoves-hermes-spark`
- [ ] Inspect `~/.local/share/hermes/profiles/pmoves-hermes-spark/config.yaml`
- [ ] Set model to NeMo 72B (`nvidia/nemotron-4-340b-instruct` via vLLM?)
- [ ] Confirm tensor parallelism (TP=2, 4, or 8)
- [ ] Return real config → update `spark.yaml` profile

### Phase 3: B850 "Knuckles" (Dual R9700 64GB ROCm)
- [ ] SSH to b850
- [ ] Install Hermes Agent
- [ ] ROCm check (`rocm-smi`, `rocminfo`)
- [ ] Create profile `pmoves-hermes-knuckles`
- [ ] Inspect config.yaml for ROCm-specific LLM settings
- [ ] Return real config → update `b850.yaml` profile

### Phase 4: 5090 / 4090 / Z890 / KVM4-1
- [ ] Context gathered from existing Claude/Codex sessions
- [ ] Cross-reference with `fleet_inventory.json` if exists
- [ ] Update all profiles with verified specs

### Phase 5: Profile Refinement PR
- [ ] Once all nodes report, create **final** `feat(hermes-profile): verified fleet profiles`
- [ ] Replace this DRAFT_PR1 with the verified version
- [ ] Close DRAFT_PR1 without merging, supersede with verified PR
