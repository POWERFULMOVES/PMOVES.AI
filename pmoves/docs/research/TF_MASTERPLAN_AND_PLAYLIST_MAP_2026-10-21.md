# Transcribe-and-Fetch Masterplan, VSS Overlap, and the Playlists: Map and Connection Table

**Date:** 2026-10-21 · **Node:** SPARK · **Lane:** L4 `docs/tf-masterplan-playlist-review` (spark-claude)
**Mode:** read-only research. Nothing was ingested, no service was started, no `.env*`/container env was read.

**Pinned trees read** (the gitlinks in this branch match the checked-out submodule HEADs):

| Submodule | Gitlink |
|---|---|
| `PMOVES-transcribe-and-fetch` (T&F) | `581e0a8141d19d4329e23ca01ab0802917e2d95d` |
| `PMOVES-Spark-VSS` | `7640d917047cf7b0fd3085eefb8282754b56bc94` |
| `PMOVES.YT` | `ebd39b7fc7507298c768fbf64826bd22265dffb0` |

Paths below are relative to the repo root. T&F paths start `PMOVES-transcribe-and-fetch/`, abbreviated **`TF/`**. VSS paths start `PMOVES-Spark-VSS/`, abbreviated **`VSS/`**. Every claim cites `file:line`. Anything I could not verify is tagged **[UNVERIFIED]**.

---

## 0. Headline findings (read these first)

1. **"MultiStrat" is not a named artifact anywhere in the tree.** A case-insensitive search for `multistrat|multi-strat|multi_strat|MultiStrategy|multi_strategy` across every submodule (`*.md,*.py,*.yaml,*.json,*.ts`, excluding `node_modules`) hits only unrelated text: hermes memory plugins, a KVM upload doc, the composio toolkit catalog, and the claim at `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md:3410`, which names "MultiStrat (PMOVES-transcribe-and-fetch)" as something to reuse. **T&F has no file, class or doc with that name.**
2. **T&F has no CLIP, CLAP or YOLO code.** Its Python (excluding vendored docs, `node_modules` and `.venv`) has zero hits for `open_clip|CLIPModel|clip_model`, `clap` and `yolo`. Its multimodal surface is: yt-dlp download with ffmpeg postprocessors, faster-whisper/Groq/OpenAI/Deepgram ASR, crawl4ai/Jina web fetch, and LLM vision calls (GPT-4o / Claude / Gemini) in a Pipecat `MultimodalAgent` (§1).
3. **The connected multi-strategy segmentation the operator is describing does exist, but it is in `PMOVES.YT`, not T&F.** `PMOVES.YT/pmoves_yt_service/yt.py:4223-4292` (`_auto_tune_segment_params`) classifies each transcript as `talk`, `dialogue`, `lyrics` or `talk-long` and retunes the chunker per profile. `/yt/emit` wires it in (`yt.py:4812-4827`) with a three-step fallback. The CLIP, CLAP, YOLO/DETR and ffmpeg stages exist as **PMOVES services** (`pmoves/services/{clip-embed,clap-embed,media-video,media-audio,ffmpeg-whisper}`), not in T&F. §2 maps what "MultiStrat" plausibly refers to.
4. **One of the two "known" playlist ids is not a playlist.** `PLILCsWKAOQGPFmCLBsln1VWvPJ6tsds5v` appears in the repo **only inside a base64 image blob** (`pmoves/docs/PMOVESCHIT/the_human_construct_neural_network.py:9`, its `.ipynb` twin, and `pmoves/docs/context/py_and_collabs/the_human_construct_neural_network.py:9`). It is a regex false positive. A read-only `yt-dlp --flat-playlist` against it returned `YouTube said: The playlist does not exist.` (measured 2026-10-21).
5. **The `ai` playlist is about 2,600 videos, not ~500.** Measured live 2026-10-21 via `yt-dlp --flat-playlist` in `pmoves-pmoves-yt-1`: `ai|2597|DARKXSIDE'S SCHOOL OF POWERFULMOVES`. The "~500" comes from a 2026-04-23 batch scan of part of the playlist (`research/PLAYLIST_BATCH_ANALYSIS.md:4-5`).
6. **The T&F masterplan contradicts itself about readiness.** `TF/masterplan/PMOVES_AI_TEAM.md:68-149` and `TF/masterplan/BACKEND_REVIEW_SUMMARY.md:171-188` say "PRODUCTION READY ✅". `TF/masterplan/PMOVES_AGENT_PLATFORM_PLAN.md:338-458` and `TF/masterplan/PROJECT_REVIEW_AND_STATUS.md:8` say "Significantly Delayed & Partially Blocked". The code supports the second account (§1.4).

---

## (a) The T&F map: agent catalog and pipeline stages

### 1.1 The masterplan folder (all 11 files plus `suportingdocs/` were read)

| File | Lines | What it is |
|---|---|---|
| `TF/masterplan/AGENT_CATALOG.md` | 187 | The agent catalog: 12 agent types with registry capability strings (table below) |
| `TF/masterplan/AGENT_COMMAND_PROTOCOL.md` | 66 | `AgentCommand {command_type, task_id, args}` sent inside Pipecat `TextFrame`s (`:11-27`, `:31`) |
| `TF/masterplan/PMOVES_AGENT_REGISTRY_SCHEMA.md` | 290 | 13-field agent metadata schema (`:11-25`) and REST API: `GET /agents`, `GET /agents/{id}`, `POST /agents/register`, `POST /agents/heartbeat`, `DELETE /agents/{id}` (`:42-46`) |
| `TF/masterplan/PMOVES_AI_TEAM.md` | 148 | "Helper teams per page" concept, plus a PMOVES orchestrator (`:11-19`). Claims production-ready (`:68-149`) |
| `TF/masterplan/PMOVES_AGENT_PLATFORM_PLAN.md` | 459 | Registry, orchestrator, Pipecat and Supabase Realtime plan. The honest status section is at `:338-383` |
| `TF/masterplan/PROJECT_REVIEW_AND_STATUS.md` | 91 | "Significantly Delayed & Partially Blocked" (`:8`). Lists the blockers (`:43-60`) |
| `TF/masterplan/Project_Status_Synthesis_Report.md` | 278 | Plan vs. reality. The dynamic LLM registry is "NOT IMPLEMENTED" (`:131-139`) |
| `TF/masterplan/BACKEND_REVIEW_SUMMARY.md` | 211 | Backend inventory. It says `main.py` is 4,684 lines (`:9`); the file is **3,278 lines** at this pin (`wc -l`). Claims "PRODUCTION READY" (`:171`) |
| `TF/masterplan/agent_llm_plan.md` / `agent_llm_plantest.md` | 422 / 452 | LiteLLM-proxy tasks 1-10. The `plantest` variant adds MCP (Task 7b) and compose hardening (Task 10) |
| `TF/masterplan/fetchfixes.md` | 37 | Four fixed bugs: circular `get_client` import, crawl4ai logger serialisation, PDF `NameError`/`TypeError` |
| `TF/masterplan/suportingdocs/` | 33 files | Fetch, crawl4ai, LLM, UI and transcribe-page plans. The pipeline-relevant ones are cited in §1.3 |

### 1.2 Agent catalog (the "map catalog")

From `TF/masterplan/AGENT_CATALOG.md`. Capability strings are the registry keys each agent would publish. Inputs and outputs are what the catalog and the code imply; the catalog has no I/O schema field.

| # | Agent | Capabilities (registry) | Inputs → Outputs | Cite | Code at this pin |
|---|---|---|---|---|---|
| 1 | Core Text Chat | `chat_completion`, `text_generation` | text → text | `:13-20` | Pipecat examples only |
| 2 | Multimodal Chat | adds `audio_input`, `audio_output`, `vision_input` | text/audio/image → text/audio | `:24-35` | `TF/pmoves-pipecat-agent/agents/multimodal_agent.py` (vision via GPT-4o / Claude 3.5 / Gemini, `:90-91`, `:347-410`) |
| 3 | Tool-Calling | `tool_calling` + per-tool | text → tool calls/results | `:39-49` | — |
| 4 | Web Fetcher | `fetch_web_content`, `crawl_web`, `extract_data{,_structured,_semantic}`, `execute_crawl_script` | URL → markdown/JSON/PDF | `:53-70` | `TF/backend/app/main.py:2507` (`GET /fetch-content`), `TF/backend/app/crawl4ai_docker_fetcher.py` |
| 5 | Search | `search{,_vector,_keyword,_hybrid}`, `query_database` | query → ranked hits | `:74-85` | `TF/backend/app/psearchworking.py` (2,640 lines) |
| 6 | Summarizer | `summarize_text`, `analyze_text` | text → summary | `:89-97` | no standalone implementation (`:96`) |
| 7 | Content Upsert | `upsert_content`, `manage_content`, `process_document` | files/MD tables → Supabase rows | `:101-110` | `TF/backend/app/pmoves_upserter.py` (943 lines) |
| 8 | Transcriber | `transcribe_audio`, `transcribe_video` | URL/audio → segments + full text | `:114-121` | `TF/backend/app/transcribe1.py`, `TF/pmoves-pipecat-agent/agents/transcribe_agent.py` |
| 9 | Supabase | `manage_database`, `create_table`, `query_data`, `upsert_data`, `manage_schema` | commands → DB ops | `:125-137` | `TF/pmoves-pipecat-agent/agents/supabase_agent.py` |
| 10-12 | RLS / Migration / Function-creation helpers | `*_rls_policy`, `generate_migration`, `*_db_function` | spec → SQL | `:141-171` | AgentCommand handlers (claimed at `AGENT_COMMAND_PROTOCOL.md:63-65`) **[UNVERIFIED — handler code not opened]** |

Orchestration contract: each agent self-registers, sends heartbeats, and talks over Pipecat. Archon queries `GET /agents` to assemble teams (`AGENT_CATALOG.md:175-184`).

### 1.3 Pipeline stages as implemented in T&F

| Stage | What it does | Segment/chunk strategy | Cite |
|---|---|---|---|
| **Ingest / download** | yt-dlp in a thread. ffmpeg postprocessors: `FFmpegExtractAudio`, `FFmpegMetadata`, `FFmpegEmbedSubtitle`, `EmbedThumbnail`. Playlist slicing via `playlistItems`/`playlistStart`/`playlistEnd` | none (whole file) | `TF/backend/app/main.py:1651-1790` (ffmpeg at `:1686`, `:1708-1742`; playlist at `:1744-1759`) |
| **Process-video entry** | `POST /process-video/` queues `process_video_with_tracking` → `transcribe1.process_video` | — | `TF/backend/app/main.py:1554-1610`, `TF/backend/app/process_video_wrapper.py:7` |
| **ASR (local)** | faster-whisper, `beam_size=1`, `vad_filter=True`, `min_silence_duration_ms=500`, `speech_pad_ms=200` | **VAD-delimited Whisper segments** (model-native), one row per segment with `watch_url&t=Ns` | `TF/backend/app/transcribe1.py:422-470` (VAD at `:442-443`) |
| **ASR (registry / Groq / OpenAI)** | `registry_service.transcribe_audio_advanced(..., response_format="verbose_json")`; provider segments copied 1:1, plus optional `speaker` | provider-native segments | `TF/backend/app/transcribe1.py:1061-1135` |
| **ASR (Groq chunked, dormant)** | pydub **5-minute** chunks, timestamps offset by chunk start | fixed 300 s windows. **Defined but not called** on the live path: `transcribe1.py:660` has no caller in `transcribe1`, and the caller at `TF/backend/app/gtrans.py:789` lives in an alternate module that `main.py` does not import (`main.py:322`) | `TF/backend/app/transcribe1.py:732-734` |
| **ASR (Pipecat TranscribeAgent)** | Groq `whisper-large-v3` / OpenAI `whisper-1` / Deepgram `nova-2` / local whisper. Declares `chunk_duration=30` | the `chunk_duration` field (`:73-75`) is **never read**: grep finds it only at its declaration | `TF/pmoves-pipecat-agent/agents/transcribe_agent.py:54-88` |
| **Store** | MD transcript + MD table → `video_transcriptions` (segments) and `video_transcriptions_full`. Web → `webpage_content`; media → `media_content`. Dedupe via RPCs `check_{webpage,text,media}_duplicate` | segment = ASR segment | `TF/backend/app/pmoves_upserter.py:309-360`, `:559`, `:647`, `:695-740` |
| **Embed (write side)** | **Not in T&F Python.** `pmoves_upserter.py` contains no embedding call. The only `embeddings.create` calls are query-side (`psearchworking.py:1358`, `vector_search.py:111`). `upsert_webpage_content` takes a precomputed `p_embedding vector(1536)` (`TF/migrations/V1_add_webpage_embeddings_and_search.sql:21-26`) | — | **[UNVERIFIED]** where segment embeddings are produced (a Supabase-side trigger or job is likely but was not found) |
| **Retrieve** | Query embedded with `text-embedding-3-small` (1536-d). `dot_product_search` returns each segment with **LAG/LEAD neighbour context** | **context window = ±1 segment at query time** | `TF/backend/app/psearchworking.py:1356-1360`; `TF/migrations/V1_add_webpage_embeddings_and_search.sql:212-255` |
| **"Three tiers"** | `fine_grained`, `contextual`, `overview`, each with its own threshold/weight/percentage/max (`psearchworking.py:583-660`) | **The tiers are not separate indexes.** All three call the same RPC, `dot_product_search` (`:1384`, `:1412`, `:1440`); only `match_count`/weights differ. The `source` label (`video_transcriptions` / `document_embeddings` / `video_transcriptions_full`) is assigned **client-side afterwards** (`:1405`, `:1433`, `:1461`) | as cited |
| **Web fetch** | crawl4ai docker (BFS/DFS deep crawl; JsonCss/LLM/Cosine/Regex/Table extraction) + Jina Reader → markdown → PDF | crawl4ai `LLMExtractionStrategy` `chunk_token_threshold` / `llm_apply_chunking` (`TF/masterplan/suportingdocs/new_test_plan.md:213-215`) | `TF/backend/app/main.py:2507`; logger workaround `TF/backend/app/crawl4ai_docker_fetcher.py:685` |

### 1.4 Registry and status reality (code, not claims)

- **Two incompatible registries exist in T&F** (the plan flags this itself at `PMOVES_AGENT_PLATFORM_PLAN.md:348`, `:381`):
  - the standalone `TF/pmoves-agent-registry/app/main.py:9-47` (table `agents`, `models.py:92-208`), which matches the masterplan schema;
  - backend routes `TF/backend/app/routes/agent_registry_routes.py:17-162` (table `agent_registry`, `TF/migrations/V6_add_models_configs_agents_tables.sql:35-51`), with a different schema.
- **The Pipecat TranscribeAgent posts results to `{backend_url}/api/transcriptions`** (`transcribe_agent.py:999`). No route with that path exists in `TF/backend/app/main.py` or `TF/backend/app/routes/*` (grep). Agent output therefore has no landing endpoint **[UNVERIFIED at runtime]**.
- The security middleware is disabled in dev and the AgentCommand protocol is not implemented in `agent_framework.py` (`PMOVES_AGENT_PLATFORM_PLAN.md:358`, `:372`). These are the plan's own words; I did not re-check the code.

### 1.5 How the T&F registry schema relates to PMOVES identity config

| T&F field (`PMOVES_AGENT_REGISTRY_SCHEMA.md:11-25`) | PMOVES equivalent | Note |
|---|---|---|
| `agent_id`, `name`, `description` | `pmoves/config/agent_registry.yaml` agent key + `name` + `description` (e.g. `:107-137`) | direct |
| `capabilities: list[str]` | none per agent. PMOVES uses `class` / `primary_type` / `secondary_type` / `role_classes` (`agent_registry.yaml:49-106`) | **gap**: PMOVES has no capability vocabulary, so T&F's 40-odd capability strings (§1.2) have no target |
| `endpoint`, `status`, `last_heartbeat` | `port` + `health` (static); liveness comes from `/healthz` probes, not heartbeats | PMOVES is declarative; T&F is self-registering |
| `dependencies`, `tags`, `config` | `nats.publishes/subscribes`, `chit_toggles`, `resilience`, `topology` | PMOVES is richer |
| `version` | `evolution_stage` | loose |
| — | `pmoves/config/signing_identity_cards.yaml` (`agent_id`, `display_name`, `glyph`, `voice`, `role`, e.g. `:186-202`) | T&F has **no signing identity**. Its agents could not sign CHIT trails |
| — | `pmoves/config/identity_vocabulary.yaml` (author-string lineage for the claim register, `:1-30`) | T&F has no equivalent |

PMOVES registers T&F as a single passive entry: `transcribe_and_fetch` (`agent_registry.yaml:2805-2829`), `port: null`, `health: null`, no NATS, all `chit_toggles` false. **None of T&F's 12 catalog agents is registered individually.**

---

## (b) "MultiStrat" as it actually exists

No file is called MultiStrat (§0.1). Three real multi-strategy mechanisms exist, and each one does a different job. Read the operator's term as one of them, or as all three.

| Candidate | Where | Strategy per modality | Implemented? |
|---|---|---|---|
| **M1. PMOVES.YT profile-autotuned segmenter** (best fit) | `PMOVES.YT/pmoves_yt_service/yt.py:4093-4292`, wired at `:4812-4827` | **Speech, by profile.** Defaults: target 30 s, gap 1.2 s, 600-1500 chars, max 60 s (`:578-582`). `dialogue`: about 20 s target, gap 0.8, ≤1200 chars, ≤45 s (`:4281-4283`). `lyrics`: 15 s, gap 0.6, 350-900 chars, ≤30 s (`:4285-4287`). `talk-long`: ≤50 s, gap ≥1.5, ≤1800 chars, ≤75 s (`:4289-4291`). Short-utterance rule: target ×0.75 when a segment has fewer than 6 words (`:4213`). Fallback order: autotuned whisper segments → fixed whisper segments → about 1000-char punctuation chunks (`:4093-4139`, `:4824-4827`). Each chunk carries `t_start` / `t_end` (`:4196`) | **Yes**, behind `YT_SEG_AUTOTUNE` (default true, `:600`). Output goes to `{HIRAG_URL}/hirag/upsert-batch` (`:4538`) |
| **M2. T&F three-tier search** | `TF/backend/app/psearchworking.py:583-660`, `:1375-1465` | **Text retrieval.** fine / contextual / overview percentage allocation + ±1-segment SQL context window | **Partly.** The tiers share one RPC, so "contextual" and "overview" do not actually query `document_embeddings` or full transcripts (§1.3) |
| **M3. T&F ASR strategy switch** | `TF/backend/app/transcribe1.py:422-470`, `:732-734`, `:1061-1135` | **Audio.** VAD segments (local) / provider segments (registry) / fixed 5-minute windows (Groq, dormant) | Local and registry paths: **yes**. 5-minute path: **dormant** |

**Per-modality coverage across the whole system.** "T&F" is the designed column; "PMOVES services" is what exists today.

| Modality | T&F (designed → built) | PMOVES services (built) | VSS (built upstream) |
|---|---|---|---|
| Speech/audio | VAD segments → built | `ffmpeg-whisper` (faster-whisper + whisperx align/diarize, `pmoves/services/ffmpeg-whisper/server.py:324`, `:478-511`); PMOVES.YT M1 segmenter | `enable_audio` transcription per chunk (`VSS/services/video-summarization/README.md:371`) |
| Audio semantics | — | `media-audio`: whisper-large-v3-turbo + hubert emotion + pyannote 3.1 (`pmoves/services/media-audio/server.py:4-11`, `:66-68`); `clap-embed`: `laion/larger_clap_music` (`pmoves/services/clap-embed/config.py:5`) | — |
| Video frames | vision_input via LLM APIs (designed) | `media-video`: every 5th frame (`FRAME_SAMPLE_RATE=5`), cap 600 frames, DETR (YOLO optional, AGPL) (`pmoves/services/media-video/server.py:3-8`, `:61-64`) | RT-CV detect/track; RT-Embed; **VLM caption per N-second chunk** |
| Image/frame embeddings | — | `clip-embed`: `openai/clip-vit-large-patch14` (`pmoves/services/clip-embed/config.py:5`) | RT-Embed (`dev-profile-search` `rtvi_embed_chunk_duration: 5`, `VSS/deploy/helm/developer-profiles/dev-profile-search/configs/vss-agent/config.yml:29`) |
| Text | crawl4ai extraction strategies | `langextract` (`pmoves/libs/langextract/providers/rule.py:17-48`: blank-line paragraphs, then `?`-sentence split, **no length cap**); `extract-worker` → Qdrant `pmoves_chunks_qwen3` + Meili (`pmoves/services/extract-worker/worker.py:25-28`, `:214-220`) | CA-RAG over captions |

---

## (c) VSS overlap

**How VSS ingests video** (`VSS/services/video-summarization/CLAUDE.md`, the in-tree service guide):

- `POST /summarize`: the RTVI-VLM service downloads the video, **chunks it**, extracts frames, and runs VLM inference **per chunk**. Per-chunk captions stream back over SSE, then **CA-RAG** aggregates them with an LLM.
- Chunk knobs are `chunk_duration` (default `0` = whole video) and `chunk_overlap_duration` (default `0`) (`VSS/services/video-summarization/README.md:365-366`). The README advises 60-120 s for videos over 5 minutes (`:531-532`).
- Profile defaults: LVS 10 s (`VSS/deploy/docker/developer-profiles/dev-profile-lvs/vss-agent/configs/config.yml:106`); search embeddings 5 s (`.../dev-profile-search/configs/vss-agent/config.yml:29`); warehouse real-time 5-8 s with 0 overlap (`VSS/deploy/docker/industry-profiles/warehouse-operations/vlm-as-verifier/realtime-config.yml:25-26`).
- Livestream mode is two-phase: `POST /v1/generate_captions` (fire-and-forget), then `POST /v1/stream_summarize` (CA-RAG over the stored captions in a time window) (`README.md:419-454`).
- Captions are stored in Elasticsearch or Milvus (`README.md:142-145`). The MCP server is `src/lvs_mcp.py`.
- **PMOVES wiring status:** "foundation landed; compose/service wiring pending" (`pmoves/docs/handoffs/SPARK_VSS_INTEGRATION_2026-07-29.md:5`). The codex home describes VSS as a developer-side blueprint, not a single container (`pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/PMOVES-Spark-VSS.md:54`).

| Concern | T&F | PMOVES today | VSS | Overlap verdict |
|---|---|---|---|---|
| Temporal chunking of video | none (audio only) | none for video frames (fixed stride in `media-video`); speech chunked by M1 | **N-second chunks + overlap** | VSS fills a PMOVES gap |
| Per-chunk visual understanding | LLM vision on single images | DETR/YOLO labels only | **VLM dense captions** (Cosmos-Reason) | VSS-only capability |
| Speech | full ASR stack | full ASR stack (×2) | optional `enable_audio` | redundant; keep PMOVES |
| Aggregation/summary | Summarizer (designed, not built) | `/yt/summarize`, `/yt/chapters` (`PMOVES.YT/.../yt.py:3475`, `:3532`) | **CA-RAG** | competing; CA-RAG is time-window aware |
| Retrieval | Supabase pgvector, 1536-d | Hi-RAG v2 (Qdrant + Neo4j + Meili) | Milvus / ES | keep Hi-RAG; VSS captions should land there |
| Agent surface | Pipecat + REST registry | A0 / Archon / MCP | `lvs_mcp.py`, VSS Agent MCP | VSS MCP is the cheapest connection point |

---

## (d) The playlists and their connect directions

Searched: the claim register, `pmoves/docs` (including `PLAYLIST_*`), `research/`, `pmoves/config/channel_monitor.json`, the live channel-monitor (`GET :8097/api/monitor/channels`, read-only), and a read-only `yt-dlp --flat-playlist` listing of the operator channel's playlists tab inside `pmoves-pmoves-yt-1` (the path `.claude/skills/pmoves-yt/SKILL.md:21-35` sanctions).

The channel-monitor registers **one** playlist: `yt:playlist:PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8` (`pmoves/config/channel_monitor.json:4-9`, confirmed live). Its stats show 10 discoveries, all failed SoundCloud items, and zero YouTube items completed (`GET /api/monitor/stats`, 2026-10-21).

### P1: `ai`, `PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8` (verified)

- **Size:** **2,597** (live, 2026-10-21). Earlier snapshots: 2,028 crawled 2026-07-28 (`pmoves/docs/research/DARKXSIDE_PLAYLIST_ANALYSIS_2026-07-28.md:5-6`); 1,795 on 2026-05-10 (`research/CATALOG_STUDIOS_AI_PLAYLIST_ANALYSIS.md:6`); 2,388 on 2026-09-24 (`AGNOTE4482PHI.t1.md:3412`). The "~500" figure is a partial scan (`research/PLAYLIST_BATCH_ANALYSIS.md:4-5`).
- **In-repo analyses:**
  - `pmoves/docs/research/DARKXSIDE_PLAYLIST_ANALYSIS_2026-07-28.md` (channel, duration, type and cluster distributions; tiered priorities)
  - `pmoves/docs/research/comprehensive-analysis/02_youtube_analysis.md` (nine clusters A-I)
  - `research/PLAYLIST_BATCH_ANALYSIS.md` (MOF relevance; 28 substantive)
  - `research/CATALOG_STUDIOS_AI_PLAYLIST_ANALYSIS.md` (curation pattern: 30-40% AI-relevant)
  - `pmoves/docs/intelligence/playlist-synthesis/STRATEGIC_SYNTHESIS_PLAYLIST_VISION.md` (7 clusters → PMOVES components). It does not name an id; it is attributed to P1 here **[UNVERIFIED]**
  - `pmoves/docs/handoffs/DARKXSIDE_PLAYLIST_PROCESSING_2026-07-28.md` (stale count "102", `:13`)
  - `pmoves/docs/specs/CATALOG_325_INGESTION_PIPELINE.md:57`
  - mavis datasets `pmoves/configs/mavis_collection/datasets/pmoves-chit-{text,multimodal}.yaml`
  - register sweeps `AGNOTE4482PHI.t1.md:3412`, `:3418`
- **Connect directions recorded:**
  1. "Process Tier 1 videos (AI/dev tutorials) **through transcribe-and-fetch** for full transcription + indexing" (`DARKXSIDE_PLAYLIST_ANALYSIS_2026-07-28.md:121`). This is the one explicit T&F connection.
  2. HF dataset (`:122`).
  3. "Wire crawled metadata into Hi-RAG" (`:123`).
  4. Persona grounding (`:124`).
  5. Fordham Hill page (`:125`).
  6. Multi-platform crawl (`:126`).
  7. Ingest and analysis into Open Notebook `darkxside` plus Neo4j `MediaRef`/`Anchor` nodes, with videoId+timestamp provenance on everything (`pmoves/docs/handoffs/darkxside-youtube-analysis-2026-09-05.md:11-22`).
  8. Pipeline "composio enumerates → yt :8077 transcribes → AgentJev-0.6B classifies" (`AGNOTE4482PHI.t1.md:3418`).
  9. Four-lens provenance index, where every extract enters "THROUGH the provenance window" (`research/analyses/2026-10-15_LIVING_PROVENANCE_PLAYLIST_DESIGN.md:21-41`).
- **State:** "No videos have been ingested yet for the DARKXSIDE `ai` playlist" via the pipeline (`.claude/skills/pmoves-yt/SKILL.md:77`). Nine priority transcripts were saved by hand under `research/transcripts` (`AGNOTE4482PHI.t1.md:3412`).

### P2: `PMOVES.AI`, `PLa64xecRY4d0` (verified; probable second playlist)

- **Size:** **1,146** (live, 2026-10-21). Earlier snapshots: 345 at creation 2026-08-11 (`pmoves/docs/operations/KILOCLAW_INSTANCE_INTEGRATION_2026-09-03.md:122`); 869 on 2026-09-25 (`pmoves/docs/research/persona/09_linkedin_content_calendar.md:127`). Note the short, non-standard id.
- **Analyses:** none dedicated. It is only inventoried (`KILOCLAW_...:122`; `09_linkedin_content_calendar.md:5`, `:116`, `:127`).
- **Connect directions recorded:** "ready-made content source for pmoves-branded posts" and persona room (`09_linkedin_content_calendar.md:5`, `:116`). There is a "heavy music additions" note (`:127`), so the M1 `lyrics` profile applies.
- **Not registered** in the channel-monitor.

### P3: unresolved

- `PLILCsWKAOQGPFmCLBsln1VWvPJ6tsds5v` is **not a playlist** (§0.4). Whoever carries it forward should drop it.
- Other channel playlists, with live head titles or sizes from the 2026-09-03 inventory (`KILOCLAW_...:120-127`):
  - science/technology `PLGupOT04oMfpropTXhkarNwWhRf966B6M` (273)
  - sustainable agriculture `PLGupOT04oMfpk0GNKR58WyIFJVCkdZXsE` (226)
  - science/state of the day `PLGupOT04oMfo7yNvvFwr-VJy4e8kd0AnX` (164)
  - science/nutrition health `PLGupOT04oMfrW5VE9CqsVP7K2h3pNECsZ` (157)
  - sustainable energy `PLGupOT04oMfrXornVDWe5LaAv00B1NBgx` (124)
  - 3d print, history, electrical, space, housing, recipes, "hoocho build list", "hy"
  - `tf` `PLGupOT04oMfqInTKTxR-rpxwCZzgDeYPl` (5 items, **Transformers franchise videos — not transcribe-and-fetch**)
  - None of these has an in-repo analysis.
- **[UNVERIFIED]** which of these the operator means by the third playlist; it may also be private or on another account. Ask the operator for the id.

---

## (e) Connection table: T&F/VSS stage → existing PMOVES service → gap

| # | Stage (T&F / VSS) | PMOVES service that already does it | Gap |
|---|---|---|---|
| 1 | Playlist/channel enumeration (T&F `main.py:1744-1759`) | **pmoves-yt** `/yt/playlist`, `/yt/channel` (`PMOVES.YT/.../yt.py:3209`, `:3322`); **channel-monitor** :8097 | `/yt/playlist` hangs on big playlists (`SKILL.md:23-25`); the monitor has never completed a YouTube item; P2 is not registered |
| 2 | Download + ffmpeg audio extract (T&F `main.py:1651-1790`) | **pmoves-yt** `/yt/download` (`yt.py:2407`) → MinIO, `ingest.file.added.v1` (`PMOVES.YT/CLAUDE.md` pipeline) | none. Do not use T&F's download path |
| 3 | ASR with timestamps (T&F `transcribe1.py:422-470`) | **ffmpeg-whisper** `/transcribe` (`pmoves/services/ffmpeg-whisper/server.py:688`), called by pmoves-yt `/yt/transcript` (`yt.py:2661-2783`) | none functionally. T&F's VAD tuning (`min_silence 500ms`, `pad 200ms`) is a candidate default for ffmpeg-whisper **[UNVERIFIED whether it already sets VAD]** |
| 4 | Diarization / emotion / acoustic features (T&F designed: `speakers`) | **media-audio** `/analyze`, `/process` (`server.py:520-526`) → `analysis.audio.v1` (`analysis_event.py:1-22`) | media-audio output is not merged into M1 chunks (no speaker or emotion on Hi-RAG chunks) |
| 5 | Transcript → chunks (M1 / T&F segments) | **pmoves-yt** `/yt/emit` M1 segmenter (`yt.py:4812-4827`) | **The M1 profile is not stamped onto the chunk payload** (`payload` = `source`, `t_start`, `t_end` only, `:4196`), so retrieval can't filter by profile. The text-path fallback `_segment_transcript` has no time anchors (`:4120-4127`) |
| 6 | Generic text chunking (crawl4ai extraction; notebook text) | **langextract** `/extract/text` (`pmoves/services/langextract/api.py:39`) via **notebook-sync** (`pmoves/services/notebook-sync/sync.py:116-142`) | `rule.py:17-48` has **no length cap**, which causes the 8191-token clipping flagged at `AGNOTE4482PHI.t1.md:3410`. **Reuse M1's `min_chars`/`max_chars` budgets** here instead of inventing a new chunker |
| 7 | Embed + index (T&F pgvector 1536-d, write side unlocated) | **extract-worker** `/ingest` → Qdrant `pmoves_chunks_qwen3` + Meili (`worker.py:25-28`, `:214`); **hi-rag-gateway-v2** `/hirag/upsert-batch` (`routes/query.py:164`) | T&F's Supabase tables (`video_transcriptions*`) are a parallel store; no bridge into Qdrant/Neo4j |
| 8 | Retrieval with neighbour context (T&F LAG/LEAD; three tiers) | **hi-rag-gateway-v2** (hybrid vector+graph+lexical) | Hi-RAG has no explicit "±1 chunk" expansion or per-tier allocation **[UNVERIFIED — rerank/graph expansion may cover it]** |
| 9 | Video frame detection (VSS RT-CV) | **media-video** `/analyze`, `/frame` (`server.py:412-423`) → `analysis.video.v1` (`:247-268`) | fixed frame stride, not time-chunked; no caption text |
| 10 | Frame/semantic video embeddings (VSS RT-Embed, 5 s) | **clip-embed** `/embed/image`, `/embed/text` (`pmoves/services/clip-embed/app.py:84`, `:108`) | **No in-repo caller.** grep for `clip-embed` / `CLIP_EMBED_URL` across `pmoves/services/**/*.py` (excluding clip-embed and tests) finds none. No keyframe → CLIP → Qdrant path |
| 11 | Audio/music embeddings | **clap-embed** `/embed/audio` (`clap-embed/app.py:121`) + NATS `audio.embed.request.v1` (`nats_responder.py:16-17`) | **No in-repo publisher** of `audio.embed.request.v1` outside clap-embed. P2's music-heavy additions would be the first consumer |
| 12 | Per-chunk VLM captioning (VSS RTVI-VLM) | **none** | **VSS-only.** Connect via VSS `/summarize` with `chunk_duration` set to the M1 `t_start`/`t_end` grid, so speech chunks and caption chunks share one time grid |
| 13 | Caption aggregation / long-video summary (VSS CA-RAG; T&F Summarizer, designed) | **pmoves-yt** `/yt/summarize`, `/yt/chapters` (`yt.py:3475`, `:3532`) | no time-window summary over stored chunks (CA-RAG's `start_time`/`end_time`) |
| 14 | Notebook / human-readable surface (T&F Obsidian dir) | **notebook-sync** → langextract → extract-worker (`sync.py:116-142`) | the handoff's Neo4j `MediaRef` writes from transcript segments are unbuilt (`darkxside-youtube-analysis-2026-09-05.md:7`) |
| 15 | Agent registry (T&F REST, self-registering) | `pmoves/config/agent_registry.yaml` (declarative) + `signing_identity_cards.yaml` | no capability vocabulary in PMOVES; T&F is registered as one passive entry (`:2805-2829`); clip-embed and clap-embed have **no** `agent_registry.yaml` entry (grep `clip`/`clap` returns nothing) |

### Simple connects (cheapest first; each reuses an existing service)

1. **Stamp the M1 `profile` onto each chunk payload** in `/yt/emit`. This is a one-line change at `yt.py:4196`.
2. **Point langextract's rule provider at M1's char budgets** to close the 8191-token clip (lane `fix/ingest-chunk-cap-multistrat`, `AGNOTE4482PHI.t1.md:3410`).
3. **Register P2 in the channel-monitor**, and route its music-heavy items to clap-embed through `audio.embed.request.v1`.
4. **Add keyframes at the M1 chunk midpoint → clip-embed → Qdrant** with the chunk's `t_start`/`t_end`. This gives every speech chunk a visual twin with no VSS dependency.
5. **Phase in VSS** (`lvs_mcp.py`) only for the per-chunk VLM caption stage (row 12), with captions upserted to Hi-RAG on the same time grid.
6. **Retire T&F's download, ASR and pgvector paths** in favour of rows 2, 3 and 7. Keep crawl4ai web fetch (row 6 input) and the masterplan's capability vocabulary (row 15) as T&F's contribution.

---

## Unverified / open items

- What "MultiStrat" means to the operator. M1 is the best fit by evidence; confirm with the operator.
- The third playlist's id. `PLILCs…` does not exist.
- Whether `STRATEGIC_SYNTHESIS_PLAYLIST_VISION.md`'s "500+ video playlist" is P1. It cites no id.
- Where T&F computes segment embeddings on write. Not found in its Python; likely Supabase-side.
- Whether ffmpeg-whisper already applies VAD parameters, and whether Hi-RAG expands neighbour chunks. Neither was opened at depth.
- The T&F helper-agent AgentCommand handlers (RLS / Migration / Function). Their existence is claimed (`AGENT_COMMAND_PROTOCOL.md:63-65`); the code was not opened.
- That the T&F backend (`transcribe-backend :8074`, per `darkxside-youtube-analysis-2026-09-05.md:7`) is running on any node. Not probed.
