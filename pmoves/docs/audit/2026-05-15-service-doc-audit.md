# Service Documentation Audit — 2026-05-15

> **Scope**: All services under `pmoves/services/`. Audited for {README presence + size, CLAUDE.md presence, tests/ dir presence}. Cross-checked against `.claude/CATALOG.md` service catalog and `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md` CHIT classification.
>
> **Branch**: `doc-audit/2026-05-15-tac-services-agnote-topology`
> **Roadmap reference**: `docs/superpowers/plans/2026-05-15-pmoves-gap-fill-roadmap.md` (companion to Wave-0 gap-fill PR #1490)

---

## Methodology

1. Walked `pmoves/services/*/` (71 entries).
2. For each: captured `README.md` byte size (0 = missing or empty), `CLAUDE.md` presence (yes/no), `tests/` directory presence (yes/no).
3. Classified:
   - **DOC-COMPLETE**: 2 or more of {README>0, CLAUDE.md, tests/}.
   - **DOC-PARTIAL**: exactly 1 of the three.
   - **DOC-MISSING**: zero of the three.
4. Cross-checked top candidates against `.claude/CATALOG.md` and `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md`.

This audit deliberately ignores `pmoves/services/<name>/requirements.txt`, `Dockerfile`, and source code completeness — those are runtime concerns. Documentation completeness is the gate here.

## Headline tally

| Class | Count | % |
|------:|------:|---|
| DOC-COMPLETE  | 10 | 14% |
| DOC-PARTIAL   | 22 | 31% |
| DOC-MISSING   | 39 | 55% |
| **Total**     | **71** | 100% |

**Cross-cutting findings**:
- 🚨 **Zero services have a `CLAUDE.md`** — subsystem context for Claude is missing across the entire fleet. This is the highest-leverage gap; even adding a 20-line `CLAUDE.md` per service materially improves Claude's grounding in that subsystem.
- 14 services have README.md files that exist but are **0 bytes** (placeholder / never written).
- 4 services have README.md files under 200 bytes (`comfyui` 108B, `comfy-watcher` 92B, `extract-worker` 146B, `mesh-agent` 351B).
- The DOC-COMPLETE 10 have substantive READMEs (mostly 4-13KB) and test dirs but still no CLAUDE.md — even the best-documented services don't expose subsystem context to Claude.

## Inventory — DOC-COMPLETE (10)

These are the exemplars. New service docs should mirror their README structure (README in `flute-gateway` is the gold standard at 8095 bytes).

| Service | README (bytes) | tests/ |
|---------|---------------:|:------:|
| agent-zero | 7664 | ✅ |
| archon | 7776 | ❌ (gap: needs tests/ + CLAUDE.md to reach exemplar) |
| channel-monitor | 12891 | ✅ |
| flute-gateway | 8095 | ✅ |
| gateway | 4244 | ✅ |
| graph-linker | 2536 | ✅ |
| hi-rag-gateway-v2 | 4768 | ✅ |
| pmoves-yt | 9204 | ✅ |
| chat-relay | 2973 | ✅ |
| evo-controller | 1105 | ✅ |

## Inventory — DOC-PARTIAL (22)

One of the three present. Quick wins.

| Service | README (bytes) | tests/ | Missing |
|---------|---------------:|:------:|---------|
| botz-gateway | 4399 | ❌ | tests, CLAUDE |
| cast-tts-gateway | 4774 | ❌ | tests, CLAUDE |
| gateway-agent | 6262 | ❌ | tests, CLAUDE |
| github-branch-cleanup | 7510 | ❌ | tests, CLAUDE |
| github-crossrepo-pr | 9473 | ❌ | tests, CLAUDE |
| github-issue-triage | 4221 | ❌ | tests, CLAUDE |
| hf-mcp-server | 3984 | ❌ | tests, CLAUDE |
| hi-rag-gateway | 1016 | ✅ | README (small), CLAUDE |
| mesh-agent | 351 | ❌ | tests, CLAUDE, README (tiny) |
| model-registry | 5961 | ❌ | tests, CLAUDE |
| retrieval-eval | 2699 | ❌ | tests, CLAUDE |
| agent_zero | 0 | ✅ | README, CLAUDE |
| common | 0 | ✅ | README, CLAUDE |
| consciousness-service | 0 | ✅ | README, CLAUDE |
| deepresearch | 0 | ✅ | README, CLAUDE |
| jellyfin-bridge | 0 | ✅ | README, CLAUDE |
| publisher | 0 | ✅ | README, CLAUDE |
| publisher-discord | 0 | ✅ | README, CLAUDE |
| tokenism-simulator | 0 | ✅ | README, CLAUDE |
| comfyui | 108 | ❌ | tests, CLAUDE, README (tiny) |
| comfy-watcher | 92 | ❌ | tests, CLAUDE, README (tiny) |
| extract-worker | 146 | ❌ | tests, CLAUDE, README (tiny) |

## Inventory — DOC-MISSING (39)

Zero of three. These are the long tail; most are likely either (a) skeletons awaiting implementation, (b) auxiliary helpers that genuinely need only a tiny README, or (c) services that should have docs but don't.

| Service | Notes (best guess from name) |
|---------|------|
| a2ui-nats-bridge | A2UI bridge — CHIT-aware per plan |
| a2ui-renderer | A2UI renderer |
| agentgym-rl-coordinator | RL coordinator — CHIT-aware per plan |
| alertmanager-discord-bridge | Observability bridge |
| analysis-echo | Analysis echo helper |
| benchmark-runner | Benchmark harness |
| container-agent | Container-side agent |
| content-provenance-gate | Provenance gate |
| evoswarm | EVO SWARM controller |
| ffmpeg-whisper | Transcription service — **P1 priority** (in top-5 fixes) |
| github-runner-ctl | GH runner control |
| gpu-orchestrator | GPU orchestrator |
| graphiti | Graphiti knowledge service |
| grayjay-plugin-host | GrayJay plugin host |
| invidious | Invidious deps |
| invidious-companion-proxy | Invidious companion |
| langextract | LangExtract worker |
| media-audio | Media audio worker |
| media-video | Media video worker |
| messaging-gateway | Messaging gateway |
| n8n | n8n self-hosted |
| nats-echo | NATS echo helper |
| node-registry | Node registry |
| notebook-sync | Notebook sync |
| pdf-ingest | PDF ingest worker |
| pmoves_yt | Underscored duplicate of pmoves-yt — investigate |
| presign | S3/MinIO presign helper |
| render-webhook | Render webhook |
| resource-detector | Resource detector |
| session-context-worker | Session context worker |
| showtime-api | Showtime API |
| supaserch | SupaSerch service — likely SHOULD have docs |
| tensorzero-config-api | TensorZero config API |
| vibevoice-realtime | VibeVoice realtime |
| vllm-orchestrator | vLLM orchestrator |
| voice-relay | Voice relay (in Known Roads `up-voice-relay`) |
| work-marshaling | Work marshaling |
| yt-cookie-refresher | YT cookies |
| yt-cookie-writer | YT cookies |

## Orphans — services in CATALOG/CHIT without a `pmoves/services/<name>/`

Per Explorer-2's audit, these names appear in `.claude/CATALOG.md` and/or `CHIT_INTEGRATION_STATUS.md` but have NO matching directory under `pmoves/services/`. Most are external dependencies (databases, monitoring stack) and are not gaps; flagged for awareness:

- **External infra**: TensorZero services (`:3030`, `:4000`, `:8123`), Supabase, Neo4j, Qdrant, Meilisearch, MinIO.
- **Monitoring stack**: Prometheus, Grafana, Loki, cAdvisor.
- **Embedded libraries**: Pipecat, SurrealDB.

No action needed unless one of these is supposed to be a local service (verify case-by-case).

## Top-5 priority fixes (this PR)

Picked for highest leverage given documented gap:

| # | Service | Current state | Fix in this PR |
|--:|---------|---------------|----------------|
| 1 | `archon` | 7.7KB README, no CLAUDE | Add `CLAUDE.md` covering Archon-as-mint architecture, ports `:8091`/`:3737`, Supabase RLS pattern, NATS subjects (`archon.mint.*.v1`, `archon.work_order.github.v1`), MCP API surface |
| 2 | `ffmpeg-whisper` | Zero docs | Add minimal `README.md` (transcription pipeline, port `:8078`, NATS subject `ingest.youtube.v1` consumer side) + `CLAUDE.md` |
| 3 | `consciousness-service` | Zero README, has tests | Add `README.md` covering persona → geometry mapping; `CLAUDE.md` |
| 4 | `cast-tts-gateway` | 4.7KB README (existing), no CLAUDE | Add `CLAUDE.md` (TTS surface + Flute-Gateway pairing) |
| 5 | `extract-worker` | 146-byte README, no CLAUDE | Expand `README.md` to cover embeddings pipeline (TensorZero embedding model format, Qdrant ingestion) + `CLAUDE.md` |

## Recommendation — TAC-tree-driven fix loop for the long tail

The 39 DOC-MISSING services should NOT be fixed by guessing what they do. Instead:

1. For each service, check if a corresponding TAC tree exists at `pmoves/configs/tac_trees/<service>.tac.yaml` or `pmoves/docs/TAC/TAC_<NAME>.md` (31 TAC docs + 34 YAML schemas exist).
2. Run `/tac:review <service>` (slash command, registered) — invokes `pmoves/tools/tac_runner.py` to produce the exact audit gaps with `agent_hint` fields suggesting which agent should fix.
3. Fix per the TAC findings, not per guesswork.

This converts the doc-fix workflow into an audit-driven loop with verifiable per-service completion criteria.

**Suggested cadence**: 5 services per follow-up PR; weekly. At ~5 per PR, the long tail (39) closes in 8 weeks. Track via `make -C pmoves docs-reconcile-check` once these services land in `living_docs_registry.yaml`.

## TODOs (out of scope this PR)

- [ ] Fix remaining 34 DOC-MISSING services via TAC-tree-driven loop.
- [ ] Investigate the `pmoves_yt` / `pmoves-yt` duplicate (likely vestige).
- [ ] Author CLAUDE.md for the 10 DOC-COMPLETE services (zero currently — biggest leverage).
- [ ] Add the 22 DOC-PARTIAL services with a small README to `living_docs_registry.yaml` so staleness is tracked.
- [ ] Substantive refresh of `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md` (52 days stale; registry now tracks it per `chore(docs-registry): track AGNOTE4482 signoff/roadmap, CHIT status, KRISS_KROSS`).
- [ ] Substantive refresh of `pmoves/docs/AGENTS/AGNOTE4482.BEATS.md` + `.FlOO$.md` (60-80 days stale; tracked at P2 / 60d).

## Verification

```bash
# Reproduce the inventory tally
{
  for d in pmoves/services/*/; do
    s=$(basename "$d")
    rb=$(stat -c%s "$d/README.md" 2>/dev/null || echo 0)
    [[ "$rb" == "" ]] && rb=0
    [[ -f "$d/CLAUDE.md" ]] && c=1 || c=0
    [[ -d "$d/tests" ]] && t=1 || t=0
    echo "$s,$rb,$c,$t"
  done
} | awk -F, '{
  has=0; if ($2>0) has++; has+=$3; has+=$4
  if (has>=2) cmp++; else if (has==1) part++; else miss++
  total++
} END { printf "Total: %d | DOC-COMPLETE: %d | DOC-PARTIAL: %d | DOC-MISSING: %d\n", total, cmp, part, miss }'
# Expected: Total: 71 | DOC-COMPLETE: 10 | DOC-PARTIAL: 22 | DOC-MISSING: 39
```
