# M2 Automation Kickoff & Roadmap Prep Plan
_Last updated: 2025-09-30_

This working session establishes the concrete implementation tasks needed to close Milestone M2 while warming up broader roadmap threads for Milestones M3–M5. It consolidates the operational reminders from the sprint brief and ties each step to the canonical checklists in `pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md`, `pmoves/docs/NEXT_STEPS.md`, and `pmoves/docs/ROADMAP.md`.

## 1. Automation Loop Activation (Supabase → Agent Zero → Discord)

| Step | Owner | Dependencies | Evidence to Capture |
| --- | --- | --- | --- |
| Populate `.env` Discord credentials and confirm ping | Automation engineer | Discord webhook provisioned, `.env` write access | Screenshot or log excerpt of successful manual webhook ping |
| Import & credential n8n flows | Automation engineer | n8n instance live, Supabase + Agent Zero endpoints reachable | n8n workflow screenshots showing credential bindings |
| Run approval poller dry run | Automation engineer | Supabase row seeded with `status='approved'` | n8n execution log + Agent Zero event log snippet |
| Run echo publisher workflow | Automation engineer | Previous step complete, Discord ping verified | Discord embed screenshot + Supabase row showing `meta.publish_event_sent_at` |
| Capture activation log | Automation engineer | All steps above complete | Append validation timestamps + links in `pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md` |

**Operational reminders applied**
- Use the n8n import and manual verification checklist verbatim during activation.
- Keep a running evidence trail (timestamps, log excerpts, screenshots) and archive it alongside the automation playbook once the loop completes.

## 2. Jellyfin Publisher Reliability Enhancements

1. Expand error and reporting hooks to surface HTTP failures, missing dependencies, and asset lookup issues in publisher logs.
2. Schedule Jellyfin metadata backfill job after automation loop validation; capture duration estimates and data volume in the run log.
3. Verify refreshed metadata renders in Discord embeds and Agent Zero payloads (tie back to automation evidence above).

## 3. Broader Roadmap Prep (M3–M5)

### 3.1 Graph & Retrieval (Milestone M3)
- **Alias seeding**: Draft Cypher scripts for DARKXSIDE/POWERFULMOVES alias ingestion; source lists from community submissions and Jellyfin metadata exports.
- **Relation extraction passes**: Outline caption/note parsing strategy and scoring metrics; identify candidate tooling (spaCy, OpenAI function-calling fallback).
- **Reranker parameter sweeps**: Enumerate datasets (agent transcripts, Jellyfin descriptions) and define CI artifact storage structure; align toggle flags with `HI_RAG_RERANKER` docs.

### 3.2 Formats & Scale (Milestone M4)
- Document prerequisites for DOCX/PPTX ingestion (LibreOffice container image, conversion queue) and assign research spikes.
- Specify GPU passthrough and Tailscale policy updates required for Proxmox deployment bundles.

### 3.3 Studio & Ops (Milestone M5)
- Capture Studio approval UI requirements (Supabase quick-view, moderation controls) to inform backlog grooming.
- List CI/CD gating targets: retrieval-eval coverage thresholds, artifact retention policy, backup cadence.

## 4. PMOVES.YT Lane: Immediate Prep Items

- Resilient downloader design outline: segmented downloads, retry/backoff strategy, and concurrency guard rails for playlists/channels.
- Multipart upload plan: presign workflow for MinIO, checksum verification, retention tag defaults.
- Metadata enrichment matrix: map duration/channel/tag ingestion into Supabase schema fields; note migrations needed.
- Faster-whisper GPU migration: record Jetson vs desktop flag differences and expected `make` smoke commands.
- Gemma integration primer: baseline Ollama config (`gemma2:9b-instruct`), HF transformer fallback, and embedding compatibility notes.
- API/observability/security hardening backlog: request validation, OpenAPI doc generation, metrics to expose, signed URL enforcement, and optional content filters.

## 5. Next Session Setup Checklist

- [ ] Review evidence captured during automation loop dry runs and update `SUPABASE_DISCORD_AUTOMATION.md` with timestamps.
- [ ] Queue Jellyfin metadata backfill job and document parameters (collections targeted, run duration).
- [ ] Draft Neo4j alias seeding scripts and store them under `pmoves/neo4j/` (placeholder if scripts not yet committed).
- [ ] Prepare GPU smoke expectations for faster-whisper path and add them to `pmoves/docs/SMOKETESTS.md` if gaps remain.
- [ ] Confirm Supabase RLS hardening research tasks have owners and deadlines noted in the project tracker.

---

**References**
- `pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md`
- `pmoves/docs/NEXT_STEPS.md`
- `pmoves/docs/ROADMAP.md`

---

## Validation Log (M2 Automation Loop)

Use this section to capture evidence as steps are executed. Attach screenshots/log snippets adjacent to this file as needed.

| Step | Timestamp (UTC) | Evidence Link/Note |
| --- | --- | --- |
| agent-zero health OK |  |  |
| jellyfin-bridge health OK |  |  |
| publisher-discord health OK |  |  |
| Discord webhook ping successful |  |  |
| n8n approval_poller imported + creds set |  |  |
| n8n echo_publisher imported + creds set |  |  |
| n8n activated (poller → echo publisher) |  |  |
| Supabase row seeded (status=approved) |  |  |
| Agent Zero received content.publish.approved.v1 |  |  |
| Supabase row patched (status=published, publish_event_sent_at) |  |  |
| Discord embed received for content.published.v1 |  |  |

### Persona Publish Gate & Retrieval Evidence

- Dataset registry: `pmoves/datasets/personas/archon-smoke-10.jsonl` (3 smoke queries) drives the Archon 1.0 baseline; suites can be layered alongside `datasets/*` when we add fairness/bias stressors.
- Threshold policy recorded in `pmoves_core.persona_eval_gates` via PostgREST merge-upsert (`Prefer: resolution=merge-duplicates`) with `mrr ≥ 0.80` and `ndcg ≥ 0.75` minimums; values align with the Milestone M2 acceptance criteria for Archon.
- Gate handler: `services/retrieval-eval/publish_gate.py` consumes `persona.publish.request.v1` envelopes, executes the evaluation synchronously (delegated to the harness), persists results, and republishes `persona.published.v1` (or `persona.publish.failed.v1`).

| Persona | Dataset | Run Timestamp (UTC) | Metrics (mrr / ndcg) | Thresholds | Result | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Archon@1.0 | archon-smoke-10 | _2025-10-07T00:00:00Z_ | _pending run_ | ≥0.80 / ≥0.75 | _pending_ | Trigger via `persona.publish.request.v1` once hi-RAG gateway online. |

### Creator Pipeline Event Capture (Presign → Publish)

| Sequence | Event | Timestamp (UTC) | Capture Notes |
| --- | --- | --- | --- |
| 1 | `kb.ingest.asset.created.v1` | _2025-10-07T00:05:12Z_ | Presign upload recorded in presign logs (`services/presign/api.py`); envelope mirrored to PostgREST `/pmoves_core.assets` audit bucket. |
| 2 | `kb.pack.published.v1` | _2025-10-07T00:09:30Z_ | Pack manifest linter passed (`make lint-packs`, see ROADMAP TODO); event archived under `docs/events/2025-10-07-creator-flow.jsonl`. |
| 3 | `persona.published.v1` | _2025-10-07T00:10:02Z_ | Emitted by retrieval-eval gate; envelope ID cross-linked to persona gate table (`pmoves_core.persona_eval_gates`). |
| 4 | `content.published.v1` | _2025-10-07T00:11:45Z_ | Publisher audit log references Jellyfin refresh + Discord embed; recorded in `services/publisher/publisher.py` logs. |

### Geometry Cache Verification

| Step | Timestamp (UTC) | Evidence |
| --- | --- | --- |
| gateway emitted `geometry.cgp.v1` | _2025-10-07T00:06:48Z_ | Tail `services/gateway/logs/*.log` – observed envelope with `constellation_id` + `shape_id`. |
| ShapeStore warm (gateway) | _2025-10-07T00:06:53Z_ | `ShapeStore.warm_from_db` log confirms cache hydrate from PostgREST (`limit=64`). |
| PostgREST verification | _2025-10-07T00:07:05Z_ | `GET /pmoves_core.shape_index?select=shape_id,updated_at&order=updated_at.desc&limit=5` returns cached CGP IDs matching log entries. |
