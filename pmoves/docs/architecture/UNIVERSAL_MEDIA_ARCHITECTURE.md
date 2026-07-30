# Universal Media Architecture — JuiceFS Mesh Storage + Content Organization

**Created:** 2026-07-28
**Node:** Knuckles (B850, AMD, residential egress)
**Status:** Architecture plan for review — extends `MEDIA_DATA_ARCHITECTURE_PLAN.md`
**Lane:** This is the **media/content organization** lane (Z890 owns JuiceFS-core migration)

## Vision: Rick and Morty's Universal TV

PMOVES.YT is not just YouTube — yt-dlp supports **1000+ sites**. Combined with Flute-Gateway (voice/TTS), WebRTC streaming, Jellyfin playback, ComfyUI (image/video generation), and JuiceFS mesh storage, PMOVES becomes a **universal media aggregation and creation platform** accessible across the entire Tailscale mesh.

Every node (5090, Z890, Knuckles, KVM4-2, SPARK) sees the same content library. Agents (Crush, HERMES) monitor and review. n8n/Activepieces orchestrate workflows. Jellyfin serves it to every screen.

## Current State

### What exists (from codebase audit)
- **MinIO** (EOL) on port 9000 — 5 buckets: `assets`, `outputs`, `pmoves-comfyui`, `cataclysm-assets`, `cataclysm-outputs`
- **JuiceFS Phase 1 PoC** — compose overlay exists (`docker-compose.juicefs.yml`), Redis metadata + S3 gateway, verified end-to-end
- **JuiceFS Phase 2** — Z890 claimed, repointing first S3 consumer (presign) to `juicefs-gateway`
- **Tailscale mesh** — Taildrop enabled, Serve planned for Jellyfin, Funnel for exit nodes
- **n8n** — own Postgres, HTTP-only service access, no S3 integration
- **Activepieces** — own Postgres + Redis, standalone on port 8087, no S3 integration
- **Publisher** — S3→Jellyfin seam via `fget_object()` download (the zero-copy target for Mode B)
- **Jellyfin** — local bind mounts (`./jellyfin-ai/media:/media`), SMB/UNC host mounts

### What's missing
- **No content-type organization** — all media dumped into generic `assets`/`outputs` buckets
- **No cross-node shared filesystem** — JuiceFS only as S3 gateway (Mode A), not POSIX mount (Mode B)
- **No `tag:storage` in Tailscale ACL** — needed for mesh storage rollout
- **No disk capacity tracking** — profiles have `storage: "NVMe SSD"` labels, no sizes
- **n8n/Activepieces** have zero S3/media access — can't trigger media workflows
- **No agent monitoring** of content (Crush/HERMES review pipeline)

## Architecture: Three-Layer Storage Stack

```
┌──────────────────────────────────────────────────────────────────┐
│ Layer 3: CONSUMERS (agents, services, UI)                        │
│  Crush ◇  │  HERMES ★  │  Jellyfin  │  n8n  │  Activepieces     │
│  Monitor + review │ Playback │ Orchestrate │ Automate            │
├──────────────────────────────────────────────────────────────────┤
│ Layer 2: JUICEFS POSIX MOUNT (shared across mesh)                │
│  /mnt/pmoves/media/                                              │
│  ├── audio/          (voice clones, TTS output, music)          │
│  │   ├── voice-clones/   (character persona voices)             │
│  │   ├── tts-output/     (Flute-Gateway synthesis)              │
│  │   └── music/          (downloaded music, creator audio)      │
│  ├── video/          (downloads, generated video, streams)      │
│  │   ├── youtube/        (PMOVES.YT downloads by channel)       │
│  │   ├── generated/      (ComfyUI/Remotion video output)        │
│  │   ├── podcasts/       (podcast ingestion)                   │
│  │   └── live-captures/  (WebRTC stream recordings)             │
│  ├── images/         (AI generation, thumbnails, art)           │
│  │   ├── comfyui/        (ComfyUI image artifacts)              │
│  │   ├── thumbnails/     (video thumbnails, auto-generated)     │
│  │   └── creator-art/    (DARKXSIDE media synthesis)            │
│  ├── transcripts/    (Whisper output, subtitles)                │
│  ├── models/         (voice models, LoRA weights, embeddings)   │
│  └── datasets/       (HuggingFace exports, training data)       │
│                                                                  │
│  Mounted on: 5090, Z890, Knuckles, KVM4-2, SPARK               │
│  Metadata: PostgreSQL (tier-data, Supabase DB)                  │
│  Data backend: MinIO (Phase 1-2) → Garage/SeaweedFS (Phase 5)   │
├──────────────────────────────────────────────────────────────────┤
│ Layer 1: S3 GATEWAY (backward compat — Mode A)                   │
│  juicefs-gateway:9000 (drop-in for minio:9000)                  │
│  All existing S3 consumers work unchanged via env var flip      │
└──────────────────────────────────────────────────────────────────┘
```

## Node Storage Topology

| Node | Role | Storage | Tailscale Tag | JuiceFS Mount |
|------|------|---------|---------------|---------------|
| **5090** | GPU inference (TTS, generation) | 2TB NVMe | `tag:inference` | `/mnt/pmoves/media` (consumer + writer) |
| **Z890** | Infrastructure coordinator | 250GB SSD (D:) + 195GB free | `tag:pmoves` | `/mnt/pmoves/media` (S3 gateway host) |
| **Knuckles** | Data-tier + ROCm (residential egress) | 1TB NVMe (ZFS) | `tag:rdna4` | `/mnt/pmoves/media` (PMOVES.YT downloader) |
| **KVM4-2** | Data-storage VPS | ~80GB | `tag:pmoves` | `/mnt/pmoves/media` (metadata host) |
| **SPARK** | Edge GPU inference | NVMe | `tag:gpu` | `/mnt/pmoves/media` (consumer) |
| **4090** | Mobile relay | 1TB | — | `/mnt/pmoves/media` (optional) |

### Metadata backend decision (blocks everything)

**Recommendation: PostgreSQL** (not Redis)
- Already running on KVM4-2 as Supabase DB
- Durable, WAL-replicated, survives reboots
- JuiceFS community edition supports Postgres natively
- One fewer service to operate (vs Redis)
- `JUICEFS_META_URL=postgres://supabase_admin:...@supabase-db:5432/postgres?search_path=juicefs_meta`

## Content Organization Schema

### Bucket → Directory Mapping

| Current S3 Bucket | JuiceFS Path | Content Type | Services Writing |
|-------------------|-------------|--------------|-----------------|
| `assets` | `/mnt/pmoves/media/video/youtube/` | Video downloads | PMOVES.YT, batch downloader |
| `outputs` | `/mnt/pmoves/media/transcripts/` | Transcription output | ffmpeg-whisper, transcribe-and-fetch |
| `pmoves-comfyui` | `/mnt/pmoves/media/images/comfyui/` | AI image generation | comfy-watcher |
| (new) | `/mnt/pmoves/media/audio/voice-clones/` | Character voice models | Flute-Gateway, Ultimate TTS |
| (new) | `/mnt/pmoves/media/audio/tts-output/` | TTS synthesis output | Flute-Gateway |
| (new) | `/mnt/pmoves/media/video/generated/` | Remotion/ComfyUI video | A2UI renderer, Archon |
| (new) | `/mnt/pmoves/media/models/` | ML weights, LoRA, embeddings | Unsloth, model registry |
| (new) | `/mnt/pmoves/media/datasets/` | HF dataset exports | yt_playlist_crawl, training |

### S3 Gateway compatibility
For Mode A (env-only swap), the gateway sees buckets as top-level dirs:
```
juicefs gateway --multi-buckets
/assets    → /mnt/pmoves/media/video/youtube/
/outputs   → /mnt/pmoves/media/transcripts/
```
New content types that don't have S3 consumers yet (voice clones, generated video) live only in the POSIX mount — no S3 bucket needed until a service requires S3 API access.

## Tailscale Exposure Strategy

### Three levels of access

| Level | Mechanism | Audience | Example |
|-------|-----------|----------|---------|
| **Mesh-private** | Tailscale Serve (HTTPS, tailnet-only) | Tailnet members | Jellyfin playback, JuiceFS S3 gateway |
| **Mesh-transfer** | Taildrop (file push/pull) | Tailnet members | Agent → agent file handoff |
| **Public** | Tailscale Funnel (HTTPS 443) | Internet | cataclysmstudios.com proxy |

### Jellyfin over Tailscale Serve
```bash
# On the node hosting Jellyfin (5090 or Z890):
tailscale serve --bg --https=443 localhost:9096
# Accessible at: https://<node>.<tailnet>.ts.net
# Set in Jellyfin admin: JELLYFIN_PublishedServerUrl=https://<node>.<tailnet>.ts.net
```
Native Jellyfin apps (Android, iOS, Android TV, Fire TV, Roku) connect via MagicDNS hostname.

### JuiceFS S3 gateway via Tailscale sidecar
```
ts-juicefs (Tailscale sidecar, tag:storage)
  → juicefs-gateway:9000 (S3 API, mesh-private)
  → Accessible from any tailnet node as: https://juicefs.<tailnet>.ts.net
```

### Agent file access (Crush, HERMES)
Agents running on any node access content via:
1. **POSIX mount** — direct file read/write at `/mnt/pmoves/media/` (fastest)
2. **S3 API** — via `juicefs-gateway:9000` from containers (Docker-native)
3. **HTTP** — via Jellyfin API for metadata/search/playback URLs

## Automation Integration

### n8n — media workflow triggers
```yaml
# Example n8n flow: "New PMOVES.YT download → transcribe → index → notify"
Trigger: NATS subject "ingest.video.downloaded.v1"
  → HTTP Request: POST transcribe-and-fetch:8000/process-video/
  → HTTP Request: POST hi-rag-gateway:8000/ingest (index transcript)
  → HTTP Request: POST discord webhook (notify)
```
n8n needs no direct S3 access — it orchestrates via HTTP APIs that already handle S3 internally.

### Activepieces — community/member automation
```yaml
# Example Activepieces flow: "Member requests video"
Trigger: Webhook from Fordham Hill tenant page
  → HTTP Request: POST pmoves-yt:8077/yt/download
  → Wait for NATS "ingest.video.downloaded.v1"
  → HTTP Request: POST jellyfin:8096/Library/Refresh
  → Email/Discord: "Your video is ready at https://jellyfin..."
```

### Crush + HERMES monitoring
- **Crush** (◇): Terminal-side review — `yt-batch-download --dry-run` shows queue, Crush approves/rejects
- **HERMES** (★): Quality gate — reviews transcripts for accuracy before indexing into Hi-RAG
- Both access content via POSIX mount at `/mnt/pmoves/media/`

## Multi-Platform Media Ingestion

### yt-dlp supported platforms (beyond YouTube)
The vendored yt-dlp fork supports **1000+ sites**. Key platforms for PMOVES content:

| Platform | URL Pattern | Content Type | Priority |
|----------|-------------|-------------|----------|
| YouTube | `youtube.com/watch?v=` | Video, audio, transcript | Tier 1 (active) |
| SoundCloud | `soundcloud.com/` | Audio, music | Tier 2 |
| Twitch | `twitch.tv/videos/` | VOD, clips | Tier 2 |
| PeerTube | `*tube*/videos/watch/` | Decentralized video | Tier 3 |
| RSS/Atom | podcast feeds | Audio podcasts | Tier 2 |
| Bitchute | `bitchute.com/video/` | Alt-tech video | Tier 3 |
| Odysee | `odysee.com/` | LBRY video | Tier 3 |

### PMOVES.YT `/yt/download` already handles non-YouTube URLs
```python
# yt.py:_infer_platform() detects the platform from URL
# _apply_provider_defaults() adjusts yt-dlp opts per platform
# The download → S3 → Supabase pipeline works for any yt-dlp-supported site
```

### Stream capture via Flute-Gateway + WebRTC
- Flute-Gateway WebSocket (`:8056`) captures duplex audio
- WebRTC session recordings can be saved to `/mnt/pmoves/media/video/live-captures/`
- Pipecat integration enables real-time voice agent session recording

## Phased Implementation

### Phase 1: POSIX Mount on Knuckles (this session lane)
1. Format JuiceFS with Postgres metadata backend
2. Mount `/mnt/pmoves/media` on Knuckles
3. Create directory structure (audio/, video/, images/, etc.)
4. Migrate existing MinIO buckets → JuiceFS paths
5. Point `yt_batch_download.py` output to `/mnt/pmoves/media/video/youtube/`

### Phase 2: Cross-Node Mount (Z890 coordination)
1. Add `tag:storage` to Tailscale ACL tagOwners
2. Mount JuiceFS on 5090, Z890
3. Wire Flute-Gateway TTS output → `/mnt/pmoves/media/audio/tts-output/`
4. Wire ComfyUI → `/mnt/pmoves/media/images/comfyui/`
5. Wire publisher to use POSIX hardlink instead of `fget_object()`

### Phase 3: Tailscale Exposure
1. `tailscale serve` Jellyfin on the hosting node
2. JuiceFS S3 gateway sidecar with `tag:storage`
3. Update `JELLYFIN_PublishedServerUrl` to MagicDNS URL
4. Test native Jellyfin app access from mobile devices

### Phase 4: Automation Wiring
1. n8n flow: NATS `ingest.video.downloaded.v1` → transcribe → index → notify
2. Activepieces flow: member request → download → Jellyfin notify
3. Crush monitoring: batch review queue
4. HERMES quality gate: transcript accuracy check

### Phase 5: Multi-Platform + Creator Pipeline
1. Add SoundCloud/podcast/RSS sources to channel-monitor
2. Wire creator pipeline: ComfyUI → images, Remotion → video, Flute → audio
3. HuggingFace dataset exports → `/mnt/pmoves/media/datasets/`
4. Persona grounding from processed content

### Phase 6: Social Media Automation (Activepieces Cloud)
1. Build COS templates for LinkedIn content scheduling
2. YouTube engagement automation (comment drafting on research videos)
3. Cross-platform content distribution (Twitter, Discord, LinkedIn)
4. Creator onboarding flows ("want PMOVES too?" → deployment wizard)
5. Wire Activepieces Cloud to self-hosted Activepieces via webhook bridge

### Phase 7: Space Monitoring + Retention
1. Enable node_exporter on all fleet nodes for Prometheus disk metrics
2. Add disk usage alerts (>85% warning, >95% critical)
3. Deploy automated cleanup cron: raw video >30 days, live captures >7 days
4. Add `node_storage_status` table to Supabase for capacity planning
5. JuiceFS volume policies: per-directory quotas and compression settings

## Operator Decisions (Resolved 2026-07-28)

### 1. JuiceFS metadata engine: PostgreSQL ✅
Use the existing Supabase Postgres instance. `JUICEFS_META_URL=postgres://...@supabase-db:5432/postgres?search_path=juicefs_meta`. Durable, WAL-replicated, one fewer service to operate.

### 2. Multi-node GPU hosting: Any GPU node can host Jellyfin or process ✅
Not one primary Jellyfin host — **every node with a GPU** can serve as Jellyfin host or transcode node. KVMs run llama.cpp for lightweight inference, passing through to GPU nodes. Node-enhanced (NVIDIA or AMD) are all compatible.

| Node | GPU | Jellyfin Transcode | llama.cpp | Role |
|------|-----|-------------------|-----------|------|
| **5090** | RTX 5090 32GB | NVENC (primary) | CUDA | GPU inference + TTS + media host |
| **Z890** | none (delegates) | VAAPI (Intel QSV) | CPU | Infrastructure coordinator |
| **Knuckles** | 2× R9700 64GB RDNA4 | VAAPI (AMD) | ROCm 7.1 HIP | Data-tier + ROCm inference + downloader |
| **KVM4-2** | none | CPU (software) | CPU (llama.cpp) | Data-storage + lightweight inference |
| **SPARK** | GB10 Blackwell | NVENC | CUDA | Edge GPU inference |
| **4090** | RTX 4090 16GB | NVENC | CUDA | Mobile relay |

**Jellyfin federation:** Each node runs Jellyfin pointing at the shared JuiceFS media mount. Clients connect to the nearest/best GPU node for transcode. `JELLYFIN_PublishedServerUrl` is per-node via Tailscale Serve.

**llama.cpp on KVMs:** KVM4-1/KVM4-2 can run lightweight llama.cpp server (CPU) for small models (Qwen2.5-3B, etc) without GPU. GPU nodes expose `llama-server` over HTTP for larger models via TensorZero routing.

**Jellyfin client/plugin review needed:**
- Jellyfin version 10.11.0 (`lscr.io/linuxserver/jellyfin:10.11.0`) — check for updates
- GrayJay plugin host (`pmoves/services/grayjay-plugin-host/`) — verify compatibility
- SSO/OIDC plugin (`pmoves/services/sso-auth/`) — verify token flow
- Plugin manifest repo URL may need refresh

### 3. Automation: MCP + A2A + Activepieces Cloud ✅
**Multi-layer automation strategy:**

**Layer 1: MCP agents** — Direct tool access for Crush/HERMES/Agent Zero
- MCP servers: docker, cipher, Hi-RAG, Tailscale, Supabase, HuggingFace
- Agents access media via MCP tool calls (list files, trigger downloads, query Hi-RAG)

**Layer 2: A2A** — Agent-to-agent task delegation
- Agent Zero A2A server (`/.well-known/agent-card.json`, `/a2a/v1/tasks`)
- Cipher A2A discovery (for cross-node agent visibility)
- Tasks: "transcribe this video", "generate voice clone", "analyze this content"

**Layer 3: Activepieces Cloud (unlimited runs)** — Social media automation
- **LinkedIn automation** via COS templates: post scheduling, content repurposing
- **YouTube engagement**: PMOVES agents help creators with comments on videos used in research
- **Social media distribution**: Cross-post PMOVES-synthesized content to multiple platforms
- **Creator collaboration**: Creators who interact with PMOVES content may want PMOVES tools
- Activepieces Cloud has unlimited runs → no self-hosted worker bottleneck
- Self-hosted Activepieces (port 8087) remains for private/internal flows

**COS template priorities:**
- LinkedIn: automated posting from processed video transcripts/persona insights
- YouTube: comment drafting on research videos, engagement tracking
- Twitter/X: cross-posting summarized content
- Discord: community notification when new content is processed

### 4. Content retention: AI lab model — transform, synthesize, analyze ✅
**Storage policy: Private AI lab, not a public media archive.**

| Content Type | Retention | Rationale |
|-------------|-----------|------------|
| Raw video downloads | 30 days post-transcription | Source is re-downloadable; transcripts are permanent |
| Transcripts | Permanent | Core knowledge base asset |
| Audio (TTS/voice clones) | Permanent | Generated assets, expensive to recreate |
| Images (ComfyUI) | Permanent | Generated assets |
| Generated video (Remotion) | Permanent | Generated assets |
| Models/weights | Permanent (versioned) | Training investments |
| Datasets (HF exports) | Permanent | Research assets |
| Live captures (WebRTC) | 7 days unless flagged | Ephemeral by nature |

**Public-facing: ZERO data exposure unless explicitly business-approved.**
- Tailscale/Pinokio mesh is private — all content stays inside the mesh
- cataclysmstudios.com public website: no raw content, only curated/synthesized outputs
- Demo/enterprise showcases: synthetic only, no real user data
- Website contact form → sessions for assistance are private (operator-gated)

**Space monitoring and scoping:**
- Prometheus alert when any node disk usage >85% (needs node_exporter — currently disabled)
- JuiceFS provides transparent dedup + LZ4/Zstd compression (reduces storage 30-50%)
- Per-content-type quotas: configurable via JuiceFS volume policies
- `make volume-list` shows Docker volume sizes
- Automated cleanup: cron job that purges raw video >30 days old from `/mnt/pmoves/media/video/youtube/` (transcripts preserved)
- Capacity planning: each node reports disk usage to Supabase `pmoves_core.node_storage_status` table

**AI lab considerations:**
- Content is meant to be **transformed, synthesized, and analyzed** — not archived as-is
- Downstream products: datasets (HF), embeddings (Qdrant), knowledge graph (Neo4j), transcripts (Hi-RAG)
- Raw media is intermediate; the knowledge artifacts derived from it are the permanent assets
- Voice clone training data: stored in `/mnt/pmoves/media/audio/voice-clones/` with per-persona subdirectories
- Research datasets: versioned and exported to HuggingFace for reproducibility
- Agent training data: interaction traces and transcripts feed shape discovery and model fitness

## Cross-References

- **Existing plan:** `pmoves/docs/handoffs/MEDIA_DATA_ARCHITECTURE_PLAN.md` (MinIO→JuiceFS migration)
- **JuiceFS compose:** `pmoves/docker-compose.juicefs.yml` (Phase 1 PoC, verified)
- **Migration spec:** `pmoves/docs/architecture/JUICEFS_OBJECT_STORE_MIGRATION.md`
- **Tailscale TAC:** `pmoves/docs/TAC/TAC_TAILSCALE.md`
- **Fleet access:** `pmoves/docs/architecture/FLEET_ACCESS_NATS_HUB.md`
- **Node inventory:** `pmoves/configs/pinokio-network-inventory.yaml`
- **Headscale ACL:** `pmoves/config/headscale/acl.yaml`
- **Activepieces:** `pmoves/activepieces/docker-compose.yml`
- **n8n:** `pmoves/docker-compose.n8n.yml`
- **Publisher (S3→Jellyfin seam):** `pmoves/services/publisher/publisher.py:1187`
- **Fordham capacity:** `pmoves/docs/pilots/fordham-hill/01-capacity-comparison.md`
