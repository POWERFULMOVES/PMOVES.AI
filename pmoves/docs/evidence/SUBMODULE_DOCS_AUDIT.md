# Submodule Documentation Audit

**Generated:** 2026-02-19 | **Source:** `submodule_layer_validate.py` output + manual review

> Captures documentation completeness across all 41 PMOVES.AI submodules. Cross-referenced with the skill registry and layer validation manifest.

---

## Summary

| Metric | Count |
|--------|-------|
| Total submodules | 41 |
| Have README | 38 |
| Have CLAUDE.md | 15 |
| Have CHANGELOG | 0 |
| Phase C audited | 8 |
| On Hardened branch | 35 |
| On main branch | 4 |
| On other branch/tag | 2 |

---

## Documentation Completeness Matrix

| Submodule | README | CLAUDE.md | CHANGELOG | Layer Evidence | Skill Registry | Branch |
|-----------|:------:|:---------:|:---------:|:--------------:|:--------------:|--------|
| PMOVES-Agent-Zero | Yes | Yes | -- | Yes | Yes | Hardened |
| PMOVES-Archon | Yes | Yes | -- | Yes | Yes | Hardened |
| PMOVES-BoTZ | Yes | Yes | -- | Yes | Yes | Hardened |
| PMOVES-BotZ-gateway | Yes | -- | -- | Yes | Yes | Hardened |
| PMOVES-DoX | Yes | Yes | -- | Yes | Yes | Hardened |
| PMOVES-HiRAG | Yes | Yes | -- | Yes | Yes | Hardened |
| PMOVES-Open-Notebook | Yes | Yes | -- | Yes | Yes | Hardened |
| PMOVES-Pipecat | Yes | Yes | -- | Yes | Yes | Hardened |
| PMOVES-tensorzero | Yes | Yes | -- | Yes | Yes | Hardened |
| PMOVES-ToKenism-Multi | Yes | Yes | -- | Yes | Yes | Hardened |
| PMOVES-Deep-Serch | Yes | Yes | -- | Yes | Yes | Hardened |
| PMOVES-Jellyfin | Yes | Yes | -- | Yes | Yes | Hardened |
| PMOVES-supabase | Yes | Yes | -- | Yes | Yes | Hardened |
| Pmoves-cipher | Yes | Yes | -- | Yes | Yes | main |
| PMOVES.YT | Yes | -- | -- | Yes | Yes | Hardened |
| PMOVES-A2UI | Yes | -- | -- | Yes | Yes | Hardened |
| PMOVES-AgentGym | Yes | -- | -- | Yes | -- | main |
| PMOVES-Creator | Yes | -- | -- | -- | -- | HEAD |
| PMOVES-Danger-infra | Yes | Yes | -- | Yes | Yes | Hardened |
| PMOVES-E2B-Danger-Room | Yes | -- | -- | Yes | Yes | Hardened |
| PMOVES-E2B-Danger-Room-Desktop | Yes | -- | -- | Yes | -- | Hardened |
| PMOVES-E2b-Spells | Yes | -- | -- | Yes | -- | Hardened |
| PMOVES-Headscale | Yes | Yes | -- | Yes | Yes | main |
| PMOVES-MAI-UI | Yes | -- | -- | -- | -- | main |
| PMOVES-Pinokio-Ultimate-TTS-Studio | Yes | -- | -- | Yes | -- | Hardened |
| PMOVES-Remote-View | Yes | -- | -- | Yes | -- | Hardened |
| PMOVES-Tailscale | Yes | -- | -- | Yes | -- | Hardened |
| PMOVES-Ultimate-TTS-Studio | Yes | -- | -- | Yes | Yes | Hardened |
| PMOVES-Wealth | Yes | -- | -- | Yes | Yes | Hardened |
| PMOVES-crush | Yes | -- | -- | Yes | Yes | Hardened |
| PMOVES-llama-throughput-lab | Yes | -- | -- | Yes | Yes | Hardened |
| PMOVES-n8n | Yes | -- | -- | -- | Yes | main |
| PMOVES-surf | Yes | -- | -- | Yes | -- | Hardened |
| PMOVES-transcribe-and-fetch | Yes | -- | -- | Yes | Yes | Hardened |
| Pmoves-AgentGym-RL | Yes | -- | -- | Yes | -- | Hardened |
| Pmoves-Health-wger | Yes | -- | -- | Yes | Yes | Hardened |
| Pmoves-Jellyfin-AI-Media-Stack | Yes | -- | -- | Yes | -- | Hardened |
| Pmoves-hyperdimensions | Yes | -- | -- | Yes | Yes | Hardened |
| pmoves-e2b-mcp-server | Yes | -- | -- | Yes | -- | Hardened |
| pmoves/integrations/archon | Yes | Yes | -- | Yes | -- | Hardened |

---

## Phase C Audit Coverage

8 critical submodules received full Phase C security audits (2026-02-16):

| Submodule | P1 Issues | P2 Issues | GREEN Areas |
|-----------|-----------|-----------|-------------|
| Agent Zero | Root containers (3), NATS no auth | -- | Secrets masking, CSRF, healthz, metrics |
| HiRAG | Cypher injection, default creds, no API wrapper, no metrics | No Dockerfile | -- |
| BoTZ | JWT fail-open, export syntax | MCP Gateway unauth | -- |
| tensorzero | Provider-proxy root, ClickHouse default creds | -- | Bearer auth, unsafe_code=forbid |
| DoX | NATS completely unauth | -- | Path traversal defense, fail-closed JWT |
| Open-Notebook | SurrealDB root:root | Auth fail-open | USER directive present |
| Pipecat | -- | No tool allowlisting, no metrics | Auth delegated to app |
| PMOVES.YT | -- | MinIO default creds, query injection | USER directive, Docker hardening |

Full details: `pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md`

---

## Gaps & Recommendations

### Missing CLAUDE.md (26 submodules)
Priority targets for context file creation:
1. **PMOVES.YT** - Core media service, heavily used
2. **PMOVES-A2UI** - UI framework, active development
3. **PMOVES-Wealth** - Financial integration
4. **PMOVES-crush** - Active development
5. **PMOVES-transcribe-and-fetch** - Media pipeline

### No CHANGELOG anywhere
Consider adopting auto-generated changelogs via `/changelog` skill for submodules with active development.

### Missing from Skill Registry
- PMOVES-AgentGym, PMOVES-E2B-Danger-Room-Desktop, PMOVES-E2b-Spells
- PMOVES-Pinokio-Ultimate-TTS-Studio, PMOVES-Remote-View, PMOVES-Tailscale
- PMOVES-surf, Pmoves-AgentGym-RL, Pmoves-Jellyfin-AI-Media-Stack
- pmoves-e2b-mcp-server, pmoves/integrations/archon

---

## Cross-References

- [Submodule Layer Validation](../SUBMODULE_LAYER_VALIDATION.md) - Layer validation manifest
- [Submodule Skill Registry](../../pmoves/configs/submodule_skill_registry.json) - Machine-readable registry
- [Submodules Catalog](../../.claude/context/submodules.md) - Context catalog
- [Documentation Map](../DOCUMENTATION_MAP.md) - CHIT-organized master index
- [Service Docs Matrix](../SERVICE_DOCS_MATRIX.md) - Service-to-docs cross-reference
- Evidence files: `pmoves/docs/evidence/submodule_layer/*.json`

---

*This document is a living artifact tracked by [CHIT_CHANGE_TRACKER.md](../CHIT_CHANGE_TRACKER.md).*
