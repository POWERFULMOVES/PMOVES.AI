# PMOVES.YT Control Worktree Review

Use this runbook when the task is not just "fix PMOVES.YT", but review the creator-control
path around it in one isolated worktree.

This is the correct lane when you need to validate:
- PMOVES.YT runtime behavior
- channel-monitor discovery and queue handoff
- transcribe-and-fetch fallback or repair posture
- Invidious / companion fallback reachability
- Jellyfin packaging or playback linkage
- Discord / BoTZ operator interaction
- model-routing posture for transcript, summarization, embeddings, rerank, and multimodal work

## Worktree setup

```bash
git worktree add ../PMOVES.AI-wt-yt-integration -b review/pmoves-yt-control
cd ../PMOVES.AI-wt-yt-integration
```

Recommended branch naming:
- `review/pmoves-yt-control`
- `feat/pmoves-yt-integration-review`
- `fix/pmoves-yt-control-plane`

## Traversal order

1. Read `pmoves/docs/PMOVES.AI PLANS/CREATOR_NETWORK_CONTROL_PLANE.md`
2. Read `pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/PMOVES.YT.md`
3. Read `pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/PMOVES-transcribe-and-fetch.md`
4. Read `pmoves/services/channel-monitor/README.md`
5. Read `pmoves/docs/AGENTS/JELLYFIN_CREATOR_WORKTREE_REVIEW.md`
6. Then inspect the live service contracts in code and compose

## Review lanes

### Lane A — PMOVES.YT runtime

- Files:
  - `PMOVES.YT/pmoves_yt_service/yt.py`
  - `PMOVES.YT/pmoves_yt_service/docs_catalog.py`
  - `PMOVES.YT/pmoves_yt_service/docs_sync.py`
  - `PMOVES.YT/pmoves_yt_service/tests/`
- Questions:
  - Is PMOVES.YT still the canonical runtime rather than a compatibility shadow?
  - Are ingest, transcript, summarize, chapters, emit, search, docs sync, and docs catalog coherent?
  - Are fallback chains explicit and current?

### Lane B — discovery and source control

- Files:
  - `pmoves/services/channel-monitor/README.md`
  - `pmoves/config/channel_monitor.json`
  - `pmoves/services/channel-monitor/`
- Questions:
  - Does channel-monitor treat PMOVES.YT as the authoritative queue target?
  - Are source classes and review modes explicit?
  - Is Google API / OAuth preferred where it should be?

### Lane C — transcript/fetch auxiliary path

- Files:
  - `PMOVES-transcribe-and-fetch/`
  - `pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/PMOVES-transcribe-and-fetch.md`
- Questions:
  - Is the auxiliary lane still additive rather than divergent?
  - Is transcript provenance preserved for downstream consumers?
  - Are repair/fallback paths documented against PMOVES.YT rather than replacing it?

### Lane D — playback and creator packaging

- Files:
  - `pmoves/tools/yt_jellyfin_smoke.py`
  - `pmoves/docs/AGENTS/JELLYFIN_CREATOR_WORKTREE_REVIEW.md`
  - Jellyfin bridge and publisher surfaces referenced there
- Questions:
  - Does PMOVES.YT emit enough metadata for Jellyfin linkage and playback?
  - Are publisher and playback paths still aligned with ingest/search contracts?

### Lane E — operator interaction and outreach

- Files:
  - `PMOVES-BoTZ/`
  - `pmoves/services/publisher-discord/`
  - `pmoves/docs/PMOVES.AI PLANS/CREATOR_NETWORK_CONTROL_PLANE.md`
- Questions:
  - Are Discord and agent-facing actions review-gated when public-facing?
  - Is creator outreach framed as attribution-aware and human-approved by default?

### Lane F — model-routing and provenance

- Files:
  - `pmoves/docs/MODEL_FABRIC_CONTRACT.md`
  - `pmoves/services/model-registry/`
  - PMOVES.YT runtime env/model references
- Questions:
  - Are models selected by role and registry mapping rather than hardcoded IDs?
  - Do transcript, summary, embedding, rerank, and multimodal outputs preserve model-family provenance?

## Minimum checks

```bash
curl -fsS http://localhost:8077/healthz
curl -fsS http://localhost:8077/yt/docs/catalog | jq .
curl -fsS http://localhost:8097/api/monitor/status | jq .
make -C pmoves channel-monitor-smoke
make -C pmoves yt-jellyfin-smoke
make -C pmoves transcribe-and-fetch-smoke
```

If model-routing changed:

```bash
make -C pmoves model-readiness
GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu
```

## Output expectations

Use a code-review mindset by default:
- findings first
- then concrete code/doc changes
- then validation evidence
- then merge order

If no findings are present, say so explicitly and call out residual risks:
- creator outreach governance
- transcript/fetch divergence
- Jellyfin linkage drift
- model-routing env drift

## Current audit snapshot

As of March 12, 2026, use these findings as the starting bias for this worktree lane:

- `channel-monitor` now supports `source_class`, but the checked-in monitor config must also
  classify sources explicitly so owned vs watched behavior is not inferred at runtime.
- `PMOVES.YT` is the canonical runtime, but its summary lane still hardcodes provider/model envs
  (`YT_SUMMARY_PROVIDER`, `YT_GEMMA_MODEL`, `HF_GEMMA_MODEL`) inside
  `PMOVES.YT/pmoves_yt_service/yt.py`.
- `PMOVES-transcribe-and-fetch` already exposes a registry-shaped `/api/v1/models` UI path, but
  its backend still carries a large static `AVAILABLE_MODELS` catalog in
  `PMOVES-transcribe-and-fetch/backend/app/app_config.py`.
- This means creator-model posture is only partially modernized:
  - the UI is closer to registry-driven
  - PMOVES.YT and transcribe/fetch runtime defaults still need convergence on shared
    model-role aliases
- Invidious + companion fallback is present and should remain part of the runtime review path for
  owned and watched YouTube sources.
- PMOVES.YT is still stronger on ingest/read/download than owned-channel mutation:
  - yt-dlp + companion + Invidious cover extraction and fallback download paths
  - PMOVES.YT now has a first owned-channel YouTube Data API control slice for playlist-add and
    comment/reply actions, but it is intentionally narrow and approval-gated
  - preview/executed actions now append to `pmoves_core.youtube_control_actions` so the creator
    lane has a durable Supabase audit trail instead of event-only visibility
  - `channel-monitor` now provides queue/list/review endpoints for those actions and approves them
    by calling PMOVES.YT control endpoints directly
  - queued control requests can now optionally notify `messaging-gateway` so Discord-ready review
    prompts come from the same request path
  - `messaging-gateway` now intercepts `ytcontrol:*` button clicks and turns them into
    `channel-monitor` review calls, closing the approval loop from Discord click to PMOVES.YT
    execution
  - broader channel-management tasks and first-class Discord interaction wiring are still follow-up
    work

## Recommended next implementation steps

1. Keep `channel-monitor` source metadata explicit in config, API payloads, and downstream PMOVES.YT
   ingest metadata.
2. Replace PMOVES.YT alias-env bridging with live registry-backed alias resolution where the
   model-registry service is available.
3. Move PMOVES-transcribe-and-fetch runtime call paths fully onto shared alias/role resolution,
   since the fallback catalog and registry compatibility seams are now PMOVES-native but the
   backend still mixes direct model ids and alias-based calls in older modules.
4. Expand the new PMOVES.YT owned-channel control plane from approval-gated playlist/comment
   actions into richer YouTube Data API coverage plus first-class Discord interaction wiring.
