# Crush/GLM-5.2 Session Lanes — 2026-07-12

> **GRAPHITI_MARK:** CRUSH-GLM52-LANES::2026-07-12
>
> Spawned from the Crush GLM-5.2 awakening session. Three pre-existing issues
> surfaced during PR #2103/#2104 review. Each is a self-contained lane with
> verified root cause, scoped fix, and no blocking dependencies on the others.

## Lane A: Kong Route Seeder Schema Fix

**Status:** CLAIMED — fixed in PR #2105
**Type:** Control-body fix (config tooling, no runtime impact)
**Effort:** Low (single-file change + Makefile include + unit test)
**Risk:** Zero — seeder has never successfully run; fixing it can't break anything

### Root Cause
`pmoves/tools/kong_route_seeder.py:_parse_model_suits()` (lines 239-244) expects
`model_id`/`provider` at top-level or under `model:` nesting. All 17 model-suit
YAMLs use one of three incompatible patterns. **0 of 17 files parse.** Silent skip
with no warning.

Additionally, `pmoves/mk/kong.mk` is never included by `pmoves/Makefile` — the
`make kong-seed-routes` target is dead code.

### Fix Scope
1. Extend `_parse_model_suits()` to understand `model_suit:`, `suit:`, and top-level `name` patterns (fallback chain, ~15 lines)
2. Add a `log.warning()` when a file is skipped due to schema mismatch
3. Add `include mk/kong.mk` to `pmoves/Makefile` (after line 180)
4. Add unit test for `_parse_model_suits` against all 3 schema patterns

### Verification
```bash
cd pmoves && python -c "
from tools.kong_route_seeder import _parse_model_suits;
suits = _parse_model_suits();
print(f'{len(suits)} suits parsed (expect 17)')
"
make kong-seed-routes  # should now work
```

---

## Lane B: Crush Configurator Z.AI Direct Provider

**Status:** CLAIMED — fixed in PR #2105
**Type:** Delivery-body feature (additive, no existing behavior changed)
**Effort:** Low-Medium (~50 lines across 2 files)
**Risk:** Low — Z.AI provider auto-disabled when `Z_AI_API_KEY` absent

### Root Cause
`pmoves/tools/crush_configurator.py` emits TensorZero as the sole provider. Running
`crush setup` on a node without TensorZero produces a broken config. The live config
on this node is hand-maintained with direct Z.AI providers — the generator has never
produced a working GLM-5.2 config.

### Fix Scope
1. Add `ZAI_SPEC` ProviderSpec (after `TENSORZERO_SPEC`, ~line 85): `env_var="Z_AI_API_KEY"`, `base_url="https://api.z.ai/api/coding/paas/v4"`, models: glm-5.2 (large), glm-5-turbo (small)
2. In `build_config()`, conditionally add `zai` to providers when `Z_AI_API_KEY` is present
3. In `_select_models()`, use Z.AI as fallback when TensorZero is absent
4. In `_fetch_tensorzero_models()` role inference (line 130), add `"glm"` to the large-model pattern
5. Add `chat_zai_glm52` to `pmoves/config/provider_catalog.yaml` under the `zai` provider (currently GLM-5.2 only under `ollama_cloud`)

### Z.AI Endpoint Reference
- Coding Plan: `https://api.z.ai/api/coding/paas/v4` (keys are endpoint-locked)
- Developer API: `https://api.z.ai/api/paas/v4/` (different keys)
- Env var: `Z_AI_API_KEY`
- Models: glm-5.2 (1M context), glm-5-turbo, glm-5v-turbo, glm-5.1

---

## Lane C: HuggingFace Agent Services + Dataset Publication

**Status:** OPEN — SPARK built 85% of the infrastructure; last 15% unclaimed
**Type:** Delivery-body feature (new services + first-time dataset publication)
**Effort:** Medium (agent service code + dataset publication + tests)
**Risk:** Low — additive services, existing infra (MCP server, tools, NATS contracts) verified working

### What SPARK Built (85% Complete)
- **Self-hosted HF MCP Server** (`pmoves/services/hf-mcp-server/`) — deployed on SPARK :8096, 5 tools, hardened container
- **4 production Python tools** — hf_model_onboard.py, hf_benchmark_runner.py, hf_model_setup.py, hf_update_tensorzero.py
- **Dataset publishing pipeline** — `publish_dataset.py` + `make hf-publish-datasets` (never run against live org)
- **430+ lines of HF model mappings** — `pmoves/config/hf_mappings.yaml`
- **Two agent registry entries** — `hf_agent` (port 8201) + `hf_research_agent` (port 8202), stage_1 (registry-only, no service code)
- **Full secrets wiring** — `HF_TOKEN` through CHIT funnel, GitHub secrets, Docker secrets
- **NATS subjects** — 6 HF subjects fully specified in nats-subjects.md
- **TAC trees** — huggingface-integration, mcp-topology, training-pipeline
- **Claude plugin** — `huggingface-skills@claude-plugins-official` enabled in settings.json

### What's Missing (the 15%)

| # | Gap | Effort | Details |
|---|-----|--------|---------|
| 1 | **HF agent service code** (port 8201) | Medium | Registry entry exists with NATS contracts (`hf.model.discovered.v1`), no `pmoves/services/hf_agent/` directory. Needs a worker that patrols HF Hub for new models matching the fleet's needs. |
| 2 | **HF research agent service code** (port 8202) | Medium | Registry entry exists (`hf.model.evaluated.v1`), no service code. Needs a worker that evaluates discovered models against fleet benchmarks. |
| 3 | **Dataset publication** | Low | `make hf-publish-datasets` never run. 3 datasets defined: pmoves-chit-text, pmoves-chit-multimodal, pmoves-agent-traces. |
| 4 | **hf-mcp-server tests** | Low-Medium | Service audit: "tests, CLAUDE missing" |
| 5 | **huggingface-skills fork sync** | Low | Commit drift `ea6ec9a6 → 221f5f78` (AGNOTE4482PHI.t1.md line 710) |

### Claim Sub-Lanes
- **C1:** Build hf_agent service (port 8201) — autonomous HF Hub patrol
- **C2:** Build hf_research_agent service (port 8202) — model evaluation worker
- **C3:** First dataset publication run + verification
- **C4:** hf-mcp-server test suite
- **C5:** huggingface-skills submodule sync

---

## Learnings for Cipher Memory

These findings should be persisted for agents performing similar tasks:

### Learning 1: Silent-Skip Anti-Pattern in Config Parsers
The Kong seeder silently skips files that don't match its expected schema. **Always
grep for `log.warning` / `log.error` near filter/guard clauses** when investigating
"the tool doesn't work" reports. If there's no warning, the tool fails silently.

### Learning 2: Endpoint-Locked API Keys
Z.AI Coding Plan keys are endpoint-locked: Coding Plan keys → `/api/coding/paas/v4`
only; Developer API keys → `/api/paas/v4/` only. Cross-use returns 401. Always verify
which endpoint a key type targets before configuring providers.

### Learning 3: Generator vs Hand-Config Drift
When a config generator exists but doesn't produce the desired output, operators
hand-maintain configs that diverge from what the generator would produce. Always
compare `generator output` vs `live config` to detect drift. Document which path
is canonical.

### Learning 4: Cross-Reference Sweeps After Renames
Mechanical renames (like skill name normalization) require body-text sweeps beyond
the frontmatter. Reviewers catch samples; agents must exhaust. Pattern: after any
rename, `rg '<old_pattern>' <scope>` and fix every match.

### Learning 5: Three Schema Patterns in One Directory
`pmoves/configs/model-suits/` has 17 YAMLs using 3 different nesting conventions
(`model_suit:`, `suit:`, top-level). Any new parser must handle all three or
explicitly declare which it supports.
