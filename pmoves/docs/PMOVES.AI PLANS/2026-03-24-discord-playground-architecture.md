# CATACLYSM STUDIOS INC — Community Playground Architecture

**Date:** 2026-03-24
**Author:** 5090-claude + DARKXSIDE
**Status:** Design approved, foundation build in progress
**TAC:** TAC_DISCORD (new), cross-refs TAC_VOICE, TAC_AGENTS, TAC_TOKENISM

## Vision

A live community playground where PMOVES.AI services are directly accessible to users. Not a notification board — an interactive experience where agents stream, beats get visualized, voices get synthesized, research gets surfaced, and content gets reviewed, all in real-time.

**Gated progressive experience:** Users level up (Student → Contributor → Builder → Faculty → DARKXSIDE) unlocking deeper access to services and agents.

**Platform-agnostic:** Discord is the first adapter. The architecture uses NATS events, MCP tools, and n8n workflows as the service layer — the chat platform is interchangeable. Research pending on open-source alternatives (Matrix, Revolt, others).

## Three Layers

### Layer 1: Foundation (org-setup)
Channels, roles, webhooks, permissions, gating rules.
- discord.js Pinokio app handles setup
- Config-driven from YAML (not hardcoded)
- Idempotent (re-runnable)
- Publishes `discord.setup.completed.v1` to NATS

### Layer 2: Services (PMOVES API surfaces)
Every PMOVES service with an API gets a Discord surface via n8n + MCP routing.
- BoTZ Gateway routes MCP tool calls
- n8n workflows handle complex multi-step flows
- Publisher-Discord wires NATS events to channels

### Layer 3: Agents (always-on personas)
Agent Zero coordinates, personas stream in channels, Flute provides voice.
- Agent signatures define persona + voice + glyph
- Persona selector auto-routes to correct TTS engine
- Streaming presence in voice channels

## Use Cases

### Beat Visualization
```
User uploads audio → Channel Monitor detects file
  → FFmpeg-Whisper extracts features
  → CHIT BPM encoder maps prosodic structure
  → Hyperdimensions renders 3D visualization
  → ComfyUI post-processes to image/video
  → Result posted to #beats-lab with CHIT attribution
```
**Trigger:** File upload in #beats-lab or "what does my beat look like?"
**Services:** Channel Monitor, BPM Encoder, Hyperdimensions, ComfyUI
**NATS:** `ingest.file.added.v1` → `tokenism.prosodic.bpm.v1` → `render.complete.v1`

### Voice Synthesis
```
User: "Read this in a dramatic voice" + text
  → Persona selector resolves intent=dramatic → Chatterbox
  → Flute-Gateway prosodic synthesis
  → Audio posted to channel or streamed to voice
```
**Trigger:** Command or message in #voice-lab
**Services:** Persona Selector, Flute-Gateway, TTS Studio (14 engines)
**NATS:** `voice.cast.completed.v1`

### Content Review
```
User: "check out this new video" + URL
  → PMOVES.YT ingests video
  → FFmpeg-Whisper transcribes
  → DeepResearch analyzes for upgrade opportunities
  → Summary + recommendations posted to #deep-research
  → If validated, Tokenism simulation runs
  → Results published to #knowledge-base
```
**Trigger:** URL in #deep-research or "review this"
**Services:** PMOVES.YT, FFmpeg-Whisper, DeepResearch, Tokenism
**NATS:** `ingest.transcript.ready.v1` → `research.deepresearch.result.v1` → `tokenism.simulation.result.v1`

### Auto-Research Feed
```
Channel Monitor detects new content from tracked channels
  → DeepResearch generates research plan
  → SupaSerch executes multi-source search
  → Ideas extracted and validated via Tokenism
  → Proven ideas published to #knowledge-base
  → Disproven ideas logged with reasoning
```
**Trigger:** Channel Monitor polling (automated)
**Services:** DeepResearch, SupaSerch, Tokenism, Hi-RAG
**NATS:** `research.deepresearch.request.v1` → `tokenism.cgp.ready.v1`

### Agent Interaction
```
User: "@agent-zero research quantum consciousness"
  → Agent Zero receives task via MCP
  → Delegates to research team (DeepResearch + Hi-RAG)
  → Results streamed to thread
  → CHIT-signed trail entry posted to #agent-trails
```
**Trigger:** @mention or command in #agent-chat
**Services:** Agent Zero, Hi-RAG, Cipher Memory
**NATS:** `agent.graphiti.signed.v1`

## Channel Structure

```
CATACLYSM STUDIOS INC
│
├── WELCOME (public)
│   ├── #welcome          → Onboarding + agent card gallery
│   ├── #waitlist         → Email capture → Supabase → n8n → invite
│   └── #announcements    → Publisher-Discord feed
│
├── AGENTS (Student+)
│   ├── #agent-trails     → Graphiti signed trails
│   ├── #agent-cards      → ComfyUI-rendered identity cards
│   ├── #agent-chat       → Interactive agent (MCP-routed)
│   └── #agent-status     → Service health feed
│
├── CREATIVE (Contributor+)
│   ├── #beats-lab        → Beat upload + CHIT visualization
│   ├── #render-lab       → ComfyUI trigger + results
│   ├── #voice-lab        → TTS demos (14 engines)
│   └── #song-lab         → Music generation (ACE-Step)
│
├── RESEARCH (Contributor+)
│   ├── #deep-research    → Research results + video reviews
│   ├── #knowledge-base   → Hi-RAG query bot
│   ├── #cipher-memory    → Agent memory queries
│   └── #tokenism-lab     → Simulation results + validated ideas
│
├── BUILDERS (Builder+)
│   ├── #dev-updates      → CI/CD notifications
│   ├── #pinokio-apps     → Launcher links + app discovery
│   ├── #docker-status    → Container health
│   └── #pr-review        → PR monitor + CodeRabbit threads
│
└── VOICE CHANNELS (Contributor+)
    ├── 🎙 Agent Voice    → Live agent TTS/STT
    ├── 🎵 Beats Room     → Audio playback + analysis
    └── 🔬 Research Lab   → Voice-driven research queries
```

## Role Gating

| Role | Access | Unlock Criteria |
|------|--------|----------------|
| Student | WELCOME + AGENTS | Join server |
| Contributor | + CREATIVE + RESEARCH + VOICE | Complete onboarding + first interaction |
| Builder | + BUILDERS | Submit a contribution (PR, workflow, content) |
| Faculty | All + moderation | Invited by DARKXSIDE |
| DARKXSIDE | Owner | — |

## Technology Stack

| Component | Role | Status |
|-----------|------|--------|
| discord.js v14 | Bot framework | Build (Pinokio app) |
| Publisher-Discord | NATS → Discord webhooks | Active (port 8094) |
| BoTZ Gateway | MCP tool routing | Active |
| n8n | Workflow automation | Active (34+ workflows) |
| NATS | Event bus | Active (all services connected) |
| Agent Zero | Agent coordination | Active (port 8080) |
| Flute-Gateway | Voice synthesis | Active (port 8055, 14 engines) |
| Persona Selector | Intent → engine routing | Shipped (Session 5) |
| BPM Encoder | Beat → CGP timeline | Shipped (Session 5) |
| Hyperdimensions | 3D visualization | Available |
| ComfyUI | Image/video rendering | Available (z890) |
| Tokenism | Idea validation | Available (port 8103) |

## Platform Migration Path

Discord is the first adapter. Design for migration to open-source:
1. All service logic lives in NATS events + MCP tools (platform-agnostic)
2. Discord-specific code isolated in adapter layer (discord.js bot + Publisher-Discord)
3. Research pending: Matrix, Revolt, Stoat, Fluxer (from DARKXSIDE AI Playlist)
4. Migration = new adapter, same NATS subjects, same MCP tools

## Implementation Phases

### Phase 1: Foundation (This Session)
- [ ] discord.js Pinokio app scaffold (install.js, start.js, pinokio.js)
- [ ] Config-driven channel/role creation from YAML
- [ ] Webhook registration per channel
- [ ] Publisher-Discord webhook URL wiring
- [ ] `discord.setup.completed.v1` NATS event

### Phase 2: Service Wiring (Next 5090 Session)
- [ ] n8n workflow: URL → ingest → research → channel post
- [ ] n8n workflow: beat upload → CHIT analysis → visualization
- [ ] MCP tool registration in BoTZ Gateway for Discord commands
- [ ] Agent Zero Discord task handler

### Phase 3: Voice + Streaming (Next 5090 Session)
- [ ] discord.js voice connection via @discordjs/voice
- [ ] Flute-Gateway WebSocket (port 8056) → Discord voice
- [ ] Real-time STT → LLM → TTS loop in voice channels

### Phase 4: Gating + Onboarding (Multi-agent)
- [ ] Role-based channel permissions
- [ ] Waitlist → Supabase → n8n → Discord invite flow
- [ ] CHIT-signed portfolio for level-up criteria
- [ ] Curriculum modules via n8n

### Phase 5: Platform Research + Migration
- [ ] Ingest "RIP Discord" video for alternative evaluation
- [ ] Evaluate Matrix, Revolt, Stoat against requirements
- [ ] Build adapter for chosen platform
- [ ] Parallel run → migration
