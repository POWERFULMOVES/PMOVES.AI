# Mavis Collection — Design

> **GRAPHITI_MARK:** Mavis::MAVIS-COLLECTION::DESIGN::2026-10-05
> **Author:** 5090-claude (Mavis on the 5090 / POWERFULMOVES)
> **Companion:** `pmoves/docs/architecture/HYPERAGINTZ_MONIKER_DESIGN.md` (HyPeRAGInTZ parent), `pmoves/docs/AGENTS/AGNOTE4482.md:1684` (HyPeRAGInTZ coined), `pmoves/configs/agents/forms/hyperagint.yaml` (per-agent identity form)
> **Branch:** `feat/mavis-collection-scaffold-2026-10-05`
> **Slice:** G — 4 sub-slices (G.1 auth, G.2 models, G.3 personas+datasets, G.4 mindmap+skills+plugins+chit)

The Mavis Collection is the **local, manifest-pointed home** for the Mavis / HyPeRAGInT orchestrator. It does NOT replace PMOVES git surfaces; it is a directory of pointers, manifests, and locally-cached state that the Mavis SDK and connected harnesses consult at runtime.

## Why a Collection (vs. just more PMOVES git)

PMOVES git holds the canonical configs (provider_catalog, datasets, forms, agents, integrations). The Collection holds:
- **Auth state** that should not be in git (Token Plan key, HF write token, Ollama Cloud key — each lives at the source-of-truth location and is read by the resolver)
- **Local caches** of models, datasets, manifests — keeps the runtime responsive without per-call git reads
- **Identity layers** — FlOO$ / DARKXSIDE / Mavis orchestrator personas sit with their reference imagery, prompts, signature moves
- **Cross-harness topology** — which harness owns which surface (Mavis/HyPeRAGInT, Hermes, Claude Code, Codex, GLM, Kimi, DeepSeek)
- **Mindmap pointers** — constellation IDs that the Cipher mindmap gateway can resolve

The Collection is **a runner of the canonical configs**, not a fork.

## Architecture (5 layers)

```
~/.mavis/collection/
├── manifest.yaml           # CGP v1.0-derived top-level manifest
├── auth/                   # Token Plan / HF / Ollama resolution + DPAPI-wrapped secrets
│   ├── minimax.json        # resolves from ~/.mmx/config.json (Token Plan source of truth)
│   ├── huggingface.json    # pointer to HF token location
│   ├── ollama_cloud.json   # Ollama Cloud URL+key (when wired)
│   └── .resolve            # 3-step probe gate helper script
├── models/                 # model suit cache (M3, M2.7, M2.7-highspeed, image-01, speech-2.8-hd, asr-1.0)
│   ├── minimax-m3.yaml
│   ├── minimax-m2.7.yaml           # (already exists in pmoves/configs/model-suits/, mirror not duplicate)
│   ├── minimax-m2.7-highspeed.yaml
│   ├── minimax-image-01.yaml
│   ├── minimax-speech-2.8.yaml
│   └── minimax-asr-1.0.yaml
├── personas/               # operator's signature moves + Mavis orchestrator
│   ├── fl00.yaml           # care-bear stares + DARKXSIDE twists
│   ├── darkxside.yaml      # helm styles from Cataclysm Studios archive
│   └── mavis-orchestrator.yaml
├── datasets/               # manifest pointers to pmoves/config/datasets.yaml (3 HF datasets)
│   ├── pmoves-chit-text.yaml
│   ├── pmoves-chit-multimodal.yaml
│   └── pmoves-agent-traces.yaml
├── mindmap/                # constellation_id pointers to /mindmap/{constellation_id}
│   └── pmoves-core.yaml
├── plugins/                # catalog pointers
│   └── Pmoves-MiniMax-Code-Plugins.yaml
├── skills/                 # catalog pointers
│   └── Pmoves-Minimax-skills.yaml
└── chit/                   # CHIT manifests (design doc + CGP v1.0 spec)
    ├── cgp_v1.0-spec.yaml
    └── hyperagintz-moniker-design.yaml
```

## Manifest schema (CGP v1.0-derived)

See `pmoves/configs/mavis_collection/manifest.schema.yaml` for the canonical schema. Summary:

```yaml
spec: pmoves.bootstrap/v1          # CGP-derived bootstrap profile
meta:
  schema_version: 1.0
  created: 2026-10-05
  last_updated: 2026-10-05
  operator: DARKXSIDE
  home: ~/.mavis/collection/
identity:
  agent: HyPeRAGInT                # or current value is identity name
  form_ref: pmoves/configs/agents/forms/hyperagint.yaml
  cross_agent_inheritance: [claude-code, kilo-code, codex, hermes, glm-coder, kimi-coder]
super_nodes:
  auth:
    - provider: minimax
      format: sk-cp
      source: ~/.mmx/config.json
      probe: 3-step-gate
  models:
    - provider: minimax
      models: [MiniMax-M3, MiniMax-M2.7, MiniMax-M2.7-highspeed, image-01, speech-2.8-hd, asr-1.0]
      routing_policy: cost-first
  datasets:
    - ref: pmoves/config/datasets.yaml#pmoves-chit-text
  personas:
    - ref: personas/fl00.yaml
  mindmap:
    - constellation_id: pmoves-core
      endpoint: pmoves/services/gateway/gateway/api/mindmap.py
  skills:
    - ref: skills/Pmoves-Minimax-skills.yaml
  plugins:
    - ref: plugins/Pmoves-MiniMax-Code-Plugins.yaml
  chit:
    - spec: pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md
    - design: pmoves/docs/architecture/HYPERAGINTZ_MONIKER_DESIGN.md
```

## Slice plan

| Sub-slice | Scope | Branch | PR |
|---|---|---|---|
| G.1 | `manifest.yaml` + `auth/` resolver + 3-step probe gate + schema validation | `feat/mavis-collection-scaffold-2026-10-05` | this PR (commit 1) |
| G.2 | `models/` — 5 MiniMax model suits + provider_catalog extension | same branch | this PR (commit 2) |
| G.3 | `personas/` + `datasets/` — FlOO$ / DARKXSIDE / Mavis + 3 HF dataset pointers | same branch | this PR (commit 3) |
| G.4 | `mindmap/` + `skills/` + `plugins/` + `chit/` — 4 surface pointers | same branch | this PR (commit 4) |

One PR, 4 commits, one review surface. Each sub-slice ships with code + tests (4 classes minimum) + LEARNINGS entry + AGNOTE CLAIM/RELEASE row.

## TBD resolutions (operator 2026-10-05, "ok to proceed")

1. **Branch layout:** 1 branch / 4 sequential commits / 1 PR ✓ (matches slice A convention; one review surface)
2. **Collection root:** `~/.mavis/collection/` ✓ (operator-confirmed; Mavis SDK owns `~/.mavis/` already)
3. **Manifest schema:** CGP v1.0 spec-derived (per `pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md`) ✓ (consistency with broader PMOVES scheme)
4. **Encryption at rest:** plaintext + Windows file ACLs everywhere EXCEPT `auth/` secrets, which get DPAPI-wrapped at session open via `Protect-File` helper ✓ (default; Mavis SDK runs with operator privileges)
5. **Key resolution path:** Token Plan key reads directly from `~/.mmx/config.json` (mmx is source of truth, single resolution path)
   - Bonus: **api_base** — `api.minimax.io` (validated by mmx smoke test, overrides catalog's `api.minimaxi.chat`)
   - Bonus: **concurrent agents** — Token Plan allows 3-4 concurrent; surfaced via `PMOVES_MAX_CONCURRENT_AGENTS` env var (advisory, not enforced)
   - Bonus: **test contract** — 4 classes minimum (manifest, resolver, probe, identity) + 5th class `cross_collection_identity` that asserts collection manifest validates against `hyperagint.yaml` form

## Cross-references

- `pmoves/docs/architecture/HYPERAGINTZ_MONIKER_DESIGN.md` — HyPeRAGInTZ integrated fabric (the parent architecture)
- `pmoves/configs/agents/forms/hyperagint.yaml` — HyPeRAGInT per-agent identity form
- `pmoves/config/provider_catalog.yaml` — provider activation catalog (extended in G.2)
- `pmoves/configs/model-suits/minimax-m2.7.yaml` — existing M2.7 model suit (extended in G.2)
- `pmoves/config/datasets.yaml` — 3 HF datasets (referenced in G.3)
- `pmoves/services/gateway/gateway/api/mindmap.py` — Neo4j-backed mindmap endpoint (referenced in G.4)
- `pmoves/integrations/_template/pmoves-integrations/` — integration contract scaffold (referenced in slice E / future)
- `pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md` — CGP v1.0 spec (manifest schema source)
- PR #3282 — slice A launcher shim (HyPeRAGInT foundation)
- PR #3184 — `--backend=` flag + `pmoves-mini claude-backend switch` (Mavis SDK overlay)