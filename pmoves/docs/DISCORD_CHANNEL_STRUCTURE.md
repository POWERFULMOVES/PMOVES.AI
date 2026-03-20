# DARKXSIDE's School of POWERFUL MOVES — Discord Server Architecture

## Overview

Discord server built as an interactive agent-powered community platform. Leverages existing PMOVES infrastructure: Publisher-Discord (NATS notifications), n8n voice agent workflows, ComfyUI rendering, TTS pipeline, and Hi-RAG knowledge search.

**Discord Nitro** — enables 100MB uploads, 256kbps voice, custom emojis as workflow triggers.

## Channel Structure

```
DARKXSIDE's School of POWERFUL MOVES
│
├── WELCOME
│   ├── #welcome          → Auto-embed with agent card gallery, rules, getting started
│   ├── #waitlist          → Supabase-backed: email → n8n webhook → segment → invite
│   └── #announcements     → Publisher-Discord feed (content.published.v1)
│
├── AGENTS
│   ├── #agent-trails      → Graphiti signed trail feed (agent.graphiti.signed.v1)
│   │                        Each trail entry shows: glyph, color, summary, resonance
│   ├── #agent-cards       → ComfyUI-rendered agent identity cards
│   │                        Generated from agent_signatures.yaml → ComfyUI workflow → embed
│   ├── #agent-chat        → Interactive voice/text agent (discord_voice_agent n8n workflow)
│   │                        RAG-aware via Hi-RAG v2, model via TensorZero
│   └── #agent-status      → Service health feed (ops.health.check.v1)
│
├── CREATIVE
│   ├── #beats-lab         → Audio upload → media-audio-analyzer → CGP envelope → indexed
│   │                        Models: MERT-v1-330M (music), HuBERT (emotion), pyannote (speakers)
│   ├── #render-lab        → ComfyUI trigger via n8n webhook + results feed
│   │                        Emoji triggers: 🎨 generate, 🔄 iterate, ✅ approve
│   ├── #voice-lab         → TTS demos via Flute Gateway (7 engines)
│   │                        !tts "text" → n8n → Flute → audio embed
│   └── #song-lab          → SongGeneration-Studio / ACE-Step integration
│                            Music creation → beats analysis → Hi-RAG indexing
│
├── RESEARCH
│   ├── #deep-research     → DeepResearch results (research.deepresearch.result.v1)
│   ├── #knowledge-base    → Hi-RAG query bot (!ask "question" → top-k results)
│   └── #cipher-memory     → Agent memory queries/updates via Cipher (port 8096)
│
├── BUILDERS
│   ├── #dev-updates       → CI/CD notifications (GitHub Actions, PR merges)
│   ├── #pinokio-apps      → App discovery, launcher links, new app announcements
│   └── #docker-status     → Container health, compose profile status
│
└── VOICE CHANNELS
    ├── 🎙 Agent Voice      → Live voice agent (Pipecat WebSocket via Flute 8056)
    ├── 🎵 Beats Room       → Audio playback + Cast TTS integration
    └── 🔬 Research Lab     → Voice-driven deep research sessions
```

## Agent Cards

Generated from `pmoves/config/agent_signatures.yaml`. Each agent gets a visual card:

| Agent | Glyph | Color | Voice | Role |
|-------|-------|-------|-------|------|
| Claude Opus | ◆ | #7C3AED Deep Violet | Analytical | Architect, security auditor |
| KiloCode | ▲ | #059669 Emerald | Architectural | VS Code features |
| Codex | ■ | #2563EB Royal Blue | Terse | Rapid code gen |
| Gemini | ★ | #D97706 Amber | Strategic | Planning, research |
| Cline | ● | #DC2626 Scarlet | Conversational | Frontend, UI prototyping |
| POWERFULMOVES | ⚡ | #F59E0B Gold | Directive | Vision, final authority |
| Crush | ◇ | #0EA5E9 Sky Blue | Companion | Terminal gateway |
| Z890 Claude | ⚙ | #1E40AF Deep Blue | Analytical | Infrastructure |
| 5090 Claude | ♫ | #9333EA Purple | Conversational | Voice/TTS pipeline |
| 4090 Claude | ◉ | #0D9488 Teal | Terse | Cast/mobile |
| DARKXSIDE | ✦ | #E11D48 Rose Crimson | Witness | Cocreation, prosodic flow |

### Card Generation Pipeline
```
agent_signatures.yaml
  → ComfyUI workflow (agent-card-gen pairing)
  → Rendered PNG with glyph, color, name, resonance domains
  → Discord embed in #agent-cards
  → Supabase storage for persistence
```

## n8n Webhook Endpoints

| Endpoint | Channel | Action |
|----------|---------|--------|
| `/webhook/discord-voice` | #agent-chat | Voice/text → Whisper → Hi-RAG → LLM → reply |
| `/webhook/waitlist` | #waitlist | Email capture → Supabase `waitlist` table → segment |
| `/webhook/comfyui-trigger` | #render-lab | Prompt → ComfyUI → render → Discord embed |
| `/webhook/tts-generate` | #voice-lab | Text → Flute Gateway → audio → Discord |
| `/webhook/beats-analyze` | #beats-lab | Audio file → media-audio → CGP → indexed |

## NATS Subjects → Discord Channels

| NATS Subject | Channel | Format |
|--------------|---------|--------|
| `agent.graphiti.signed.v1` | #agent-trails | Trail entry embed with glyph + color |
| `ingest.transcript.ready.v1` | #announcements | New transcript available |
| `ingest.summary.ready.v1` | #announcements | Summary generated |
| `content.published.v1` | #announcements | New content published |
| `research.deepresearch.result.v1` | #deep-research | Research results embed |
| `voice.cast.completed.v1` | #beats-room | Cast playback completed |
| `analysis.audio.v1` | #beats-lab | Audio analysis results |

## Waitlist Segments

| Segment | Description | Auto-role |
|---------|-------------|-----------|
| Student | Learning AI/coding, exploring CHIT | @Student |
| Builder | Contributing code, building integrations | @Builder |
| Enterprise | Commercial licensing, custom deployment | @Enterprise |
| Investor | Funding, advisory | @Investor |

## Implementation Phases

1. **Phase 1 (This Session):** Document structure, create webhook endpoints in n8n
2. **Phase 2:** Set up Discord server channels, roles, permissions
3. **Phase 3:** Wire Publisher-Discord to new channel webhooks
4. **Phase 4:** ComfyUI agent card generation pipeline
5. **Phase 5:** Voice channel integration (Pipecat WebSocket)
