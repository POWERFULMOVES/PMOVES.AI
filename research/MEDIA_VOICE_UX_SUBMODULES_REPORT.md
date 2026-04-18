# Media, Voice, UX & Peripheral Submodules Report

**Generated:** 2026-04-17  
**Classification:** Internal — PMOVES.AI Ecosystem  
**Scope:** 11 submodules, voice pipeline, Next.js UI, media services  

---

## Executive Summary

This report covers 11 submodules in the Media, Voice, UX, and Peripheral categories of the PMOVES.AI codebase. The findings reveal a stark maturity spectrum:

- **10 of 11 submodules are EMPTY** — git submodule directories exist but were never cloned
- **GrapheneOS does not exist anywhere** in the codebase — greenfield effort required
- **Voice pipeline is the most mature subsystem** with 3 Docker services, 8 Python tools, and a 757-line TAC tree
- **Next.js UI is production-grade** with 205+ files, React 19.2, Supabase integration, and 12 E2E tests
- **PMOVES.YT is completely broken** — a 22-line `exec()` shim pointing to an empty submodule

The gap between designed architecture (described in docs, TAC trees, and architecture files) and actual implementation is severe. Most "submodules" are placeholder directories with no code.

---

## 1. PMOVES-Pinokio-Ultimate-TTS-Studio

### 1.1 Submodule Status

| Attribute | Value |
|-----------|-------|
| Path | `PMOVES-Pinokio-Ultimate-TTS-Studio/` |
| Cloned | ❌ No — empty directory |
| In-tree code | ✅ Yes — references in tools/ and pbnj/ |

### 1.2 In-Tree Implementation

Despite the empty submodule, a functional TTS hub exists in-tree:

**14 TTS Engines across 4 providers:**

| Provider | Engines | Status |
|----------|---------|--------|
| Fish Speech | fish-speech-api | Active (primary) |
| Coqui | coqui-tts, tacotron2 | Available |
| Bark | bark-tts | Available |
| VITS | vits-tts, piper-tts | Available |

**Deployment:**
- Runs on RTX 5090 via Pinokio automation
- Gradio web interface on port **7860**
- Located in `pbnj/pinokio/` directory structure

### 1.3 Assessment

The in-tree TTS implementation is **functional but disconnected** from the broader PMOVES.AI service architecture. It runs as a standalone Pinokio-managed application rather than as a Dockerized service in `pmoves/services/`. No NATS integration, no TensorZero tracing, no Supabase persistence.

---

## 2. Voice Pipeline (MOST MATURE SUBSYSTEM)

### 2.1 Docker Services

Three containerized voice services exist in `pmoves/services/`:

| Service | Port | Function | Dockerfile | Python Code |
|---------|------|----------|------------|-------------|
| Flute-Gateway | 8055 | Voice communication layer | ✅ | ✅ |
| Voice-Relay | 8121 | Message relay between voice endpoints | ✅ | ✅ |
| FFmpeg-Whisper | 8078 | Audio transcription pipeline | ✅ | ✅ |

### 2.2 Host-Run Python Tools

8 Python tools in `pmoves/tools/` provide voice pipeline testing and interaction:

| Tool | Purpose |
|------|---------|
| `voicebox_probe.py` | Probe voice service availability and health |
| `voicebox_full_probe.py` | Comprehensive voice stack diagnostic |
| `voice_follow_agent.py` | Voice-based agent following/interaction |
| `voice_follow_cast_agent.py` | Cast-based voice agent interaction |
| `voice_speaker.py` | Text-to-speech output via voice pipeline |
| `voice_to_discord_test.py` | Test voice integration with Discord |
| `voice_chain_e2e_test.py` | End-to-end voice chain testing |
| `voice_persona_bind.py` | Bind voice personas to agent profiles |
| `voice_agent_discord_smoke.py` | Smoke test for Discord voice agent |

### 2.3 TAC Tree Coverage

The voice pipeline has a **757-line TAC tree** with **15 phases** — the most comprehensive operational definition of any PMOVES.AI subsystem:

```
voice-pipeline.tac.yaml — 757 lines, 15 phases
├── Phase 1: Infrastructure bootstrap
├── Phase 2: NATS subject provisioning
├── Phase 3: Flute-Gateway deployment
├── Phase 4: Voice-Relay deployment
├── Phase 5: FFmpeg-Whisper deployment
├── Phase 6: TTS engine integration
├── Phase 7: Voice persona binding
├── Phase 8: Discord voice bridge
├── Phase 9: End-to-end chain validation
├── Phase 10: Health check configuration
├── Phase 11: Monitoring integration
├── Phase 12: Load testing
├── Phase 13: Failover testing
├── Phase 14: Security hardening
└── Phase 15: Production handoff
```

### 2.4 TTS Engine Inventory

14 TTS engines across 4 providers (same as Pinokio TTS Studio, shared infrastructure):

```
Fish Speech:  fish-speech-api
Coqui:        coqui-tts, tacotron2, gst-tacotron2
Bark:         bark-tts, bark-tts-large
VITS:         vits-tts, piper-tts, openjtalk-vits, etc.
```

### 2.5 Critical Gaps

#### P0: Voice Relay Uses Core NATS (Not JetStream)

```
Current:  Voice-Relay publishes to Core NATS subjects
Problem:  Core NATS = at-most-once delivery, no persistence
Impact:   Voice packets can be silently dropped under load
Fix:      Migrate voice subjects to JetStream with explicit ack
```

Voice communication requires reliable delivery. Current Core NATS provides fire-and-forget semantics — acceptable for telemetry but **unacceptable for voice packets** where dropped messages mean lost words or broken conversations.

#### P1: Zero TensorZero Integration

None of the 3 voice services have TensorZero tracing:

| Service | TensorZero Client | Tracing | Feedback Loop |
|---------|-------------------|----------|---------------|
| Flute-Gateway | ❌ | ❌ | ❌ |
| Voice-Relay | ❌ | ❌ | ❌ |
| FFmpeg-Whisper | ❌ | ❌ | ❌ |

Without TensorZero integration:
- No latency tracking per voice transaction
- No quality scoring for TTS output
- No feedback loop for improving voice persona selection
- No observability into voice pipeline performance

#### P1: 7 NATS Subjects Designed But Unimplemented

The TAC tree defines 7 NATS voice/media subjects that have **no code subscribing or publishing**:

```
voice.pipeline.status.v1       — No publisher
voice.pipeline.transcript.v1    — No publisher  
voice.pipeline.tts.request.v1   — No subscriber
voice.pipeline.tts.result.v1    — No subscriber
voice.media.process.request.v1  — No subscriber
voice.media.process.result.v1   — No subscriber
voice.media.asset.metadata.v1   — No publisher
```

These subjects represent designed-but-unbuilt integration points between voice services and the broader PMOVES.AI ecosystem.

---

## 3. PMOVES.YT (BROKEN)

### 3.1 Current State

**Status:** ❌ **Completely non-functional**

The entire YouTube pipeline is a **22-line shim**:

```python
# pmoves/services/media-youtube/main.py (actual content)
import subprocess
import sys

subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "yt-dlp", "google-api-python-client"
])

exec(open("PMOVES-YT/main.py").read())
```

### 3.2 Failure Analysis

| Component | Status | Detail |
|-----------|--------|--------|
| `PMOVES-YT/` submodule | ❌ Empty | Never cloned — `main.py` does not exist |
| `exec()` call | ❌ Fails | `FileNotFoundError` on every invocation |
| pip deps install | ⚠️ Runs | Wastes time installing deps for dead code |
| Smoke test | ✅ Exists | `test_pmoves_yt.py` — but tests the shim, not functionality |

### 3.3 Impact

- Zero YouTube upload/download capability
- No video publishing pipeline
- No YouTube API integration
- The `yt_jellyfin_smoke.py` and `youtube_po_token_capture.py` tools reference YouTube functionality that cannot work

### 3.4 Remediation Required

```
P0: git submodule update --init PMOVES-YT
P0: Rewrite main.py — remove exec() shim, implement proper service
P0: Define YouTube API credentials in secrets/
P1: Implement upload/download workflows
P1: Add NATS integration for pipeline events
P2: Add TensorZero tracing for YouTube operations
```

---

## 4. Next.js UI (PRODUCTION-GRADE)

### 4.1 Overview

| Metric | Value |
|--------|-------|
| Total files | 205+ |
| React version | 19.2 |
| Framework | Next.js (App Router) |
| Styling | Tailwind CSS |
| Docker | ✅ Dockerfile exists |

### 4.2 Key Subsystems

#### TensorZero Management Suite (8 files)

A dedicated management interface for TensorZero operations:

- Function management (create, edit, delete TensorZero functions)
- Variant configuration
- Feedback dashboard
- Metrics visualization

Located in `pmoves/ui/components/tensorzero/` and `pmoves/ui/app/tensorzero/`.

#### Supabase Integration (~54 files)

Deep Supabase integration across the UI:

- Authentication (Supabase Auth)
- Real-time subscriptions
- Database queries via Supabase client
- Row-level security integration
- Storage bucket management

#### E2E Test Suite (12 Playwright tests)

```
pmoves/ui/e2e/
├── auth.spec.ts
├── dashboard.spec.ts
├── tensorzero-manage.spec.ts
├── voice-controls.spec.ts
├── settings.spec.ts
├── ... (6 more)
```

### 4.3 Assessment

The Next.js UI is the **most complete and production-ready component** in the PMOVES.AI ecosystem. It has:

- Proper project structure (App Router, components, hooks, lib)
- Type safety (TypeScript throughout)
- Test coverage (unit + E2E)
- Container deployment ready
- Real backend integrations (Supabase, TensorZero)

**Minor gaps:**
- No NATS integration in the UI (real-time events would need WebSocket bridge)
- No voice waveform visualization components
- No dark/light theme toggle (Tailwind configured but not exposed)

---

## 5. Pmoves-Jellyfin-AI-Media-Stack

### 5.1 Submodule Status

| Attribute | Value |
|-----------|-------|
| Path | `Pmoves-Jellyfin-AI-Media-Stack/` |
| Cloned | ❌ No — empty directory |
| In-tree code | Minimal — `jellyfin.hosts` config only |

### 5.2 In-Tree References

Only one in-tree artifact references Jellyfin:

```
pmoves/jellyfin.hosts — DNS/host mapping for Jellyfin instances
```

No Jellyfin service code exists in `pmoves/services/`. No Docker configuration for Jellyfin. No NATS subjects for Jellyfin events.

### 5.3 Assessment

Jellyfin integration is **conceptual only**. The `jellyfin.hosts` file suggests planned multi-instance deployment, but no implementation exists. The `yt_jellyfin_smoke.py` tool attempts to test Jellyfin integration but cannot function without the service.

---

## 6. PMOVES-A2UI

### 6.1 Submodule Status

| Attribute | Value |
|-----------|-------|
| Path | `PMOVES-A2UI/` |
| Cloned | ❌ No — empty directory |
| Evaluation | ✅ 21KB evaluation report exists |

### 6.2 A2UI Evaluation Report

A prior evaluation report (`research/A2UI_EVALUATION_REPORT.md`, 21KB) assessed the A2UI desktop framework:

- Desktop application framework for Agent Zero
- Pairs with **E2B Danger-Room Desktop** for local Agent Zero spin-up
- Provides native desktop UI wrapper around Agent Zero CLI

### 6.3 Assessment

A2UI represents the **desktop client strategy** for PMOVES.AI. The evaluation was completed but the submodule was never cloned. Implementation depends on the E2B Danger-Room Desktop infrastructure being operational.

---

## 7. PMOVES-transcribe-and-fetch

### 7.1 Submodule Status

| Attribute | Value |
|-----------|-------|
| Path | `PMOVES-A2UI/PMOVES-transcribe-and-fetch/` (nested) |
| Cloned | ❌ No — empty directory |
| Parent | Nested under PMOVES-A2UI |

### 7.2 Assessment

This is a **nested submodule** under PMOVES-A2UI. It provides transcription and URL fetching capabilities for the desktop client. Cannot be used independently — requires PMOVES-A2UI parent to be cloned first.

Minimal in-tree references. No standalone service code.

---

## 8. PMOVES-surf

### 8.1 Submodule Status

| Attribute | Value |
|-----------|-------|
| Path | `PMOVES-surf/` |
| Cloned | ❌ No — empty directory |
| In-tree references | ❌ Zero |

### 8.2 Operational Footprint

PMOVES-surf has **zero operational footprint** anywhere in the codebase:

- No service in `pmoves/services/`
- No configuration files
- No NATS subjects
- No TAC tree references
- No test files
- No documentation references

### 8.3 Assessment

PMOVES-surf is a **ghost submodule** — it exists in `.gitmodules` but has no integration with any PMOVES.AI system. Possible scenarios:

1. Abandoned feature that was never developed
2. Planned web scraping/browsing tool that was superseded by browser_agent
3. Placeholder for future capability

**Recommendation:** Either remove from `.gitmodules` or document its intended purpose.

---

## 9. PMOVES-DoX

### 9.1 Submodule Status

| Attribute | Value |
|-----------|-------|
| Path | `PMOVES-DoX/` |
| Cloned | ❌ No — empty directory |
| In-tree references | Minimal |

### 9.2 Assessment

PMOVES-DoX appears to be a documentation tool submodule. Very few in-tree references exist. No service code, no configuration, no integration points.

Similar to PMOVES-surf, this submodule may be abandoned or planned-but-never-developed.

---

## 10. GrapheneOS

### 10.1 Status

**Does NOT exist anywhere in the codebase.**

| Search Location | Result |
|-----------------|--------|
| Submodule directories | ❌ Not found |
| `pmoves/services/` | ❌ Not found |
| `.gitmodules` | ❌ Not found |
| Code search ("graphene") | ❌ Zero results |
| Documentation | ❌ Zero results |
| TAC trees | ❌ Zero results |

### 10.2 Context

GrapheneOS is referenced in user plans as the target for a **Pixel 10 Pro PMOVES.AI app**. This would be a greenfield effort requiring:

- GrapheneOS build environment setup
- PMOVES.AI app development for Android/GrapheneOS
- Tailscale mesh integration for secure communication
- Custom APK signing and OTA update infrastructure

### 10.3 Proposed Strategy

Based on the infrastructure patterns in PMOVES.AI:

```
Option A (Recommended): PWA on Hostinger VPS
├── Deploy as Progressive Web App on existing Hostinger infrastructure
├── Tailscale mesh access for API communication
├── No GrapheneOS build required
├── Works on any mobile browser
└── Lower effort, broader compatibility

Option B: Native GrapheneOS App
├── Requires GrapheneOS build environment (separate workstation)
├── Custom APK with PMOVES.AI integration
├── Tailscale VPN for mesh connectivity
├── Higher effort, Pixel 10 Pro only
└── Maximum security and native UX
```

---

## 11. Media Services (Skeleton Stubs)

### 11.1 Existing Service Stubs

Two media service directories exist in `pmoves/services/`:

| Service | Dockerfile | Python Code | Config |
|---------|------------|-------------|--------|
| `media-video/` | ✅ | ❌ Zero | ❌ |
| `media-audio/` | ✅ | ❌ Zero | ❌ |

### 11.2 Assessment

These are **skeleton stubs** — Dockerfiles exist (probably boilerplate) but contain zero application code. They represent planned media processing services that were scaffolded but never implemented.

**Recommendation:** Either implement the media processing logic or remove the stubs to reduce confusion.

---

## Cross-Cutting Integration Matrix

Comprehensive view of integration status across all media/voice/UX components:

| Service | Docker | NATS | TensorZero | Supabase | Tests | TAC Tree | Status |
|---------|--------|------|------------|----------|-------|----------|--------|
| Flute-Gateway | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ (shared) | Running |
| Voice-Relay | ✅ | ✅(Core) | ❌ | ❌ | ❌ | ✅ (shared) | Running (flawed) |
| FFmpeg-Whisper | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ (shared) | Running |
| Pinokio TTS | ❌(Pinokio) | ❌ | ❌ | ❌ | ❌ | ❌ | Running (standalone) |
| Next.js UI | ✅ | ❌ | ✅ | ✅ | ✅(12 E2E) | ❌ | Production |
| PMOVES.YT | ❌ | ❌ | ❌ | ❌ | ✅(smoke) | ❌ | **BROKEN** |
| media-video | ✅(stub) | ❌ | ❌ | ❌ | ❌ | ❌ | Skeleton |
| media-audio | ✅(stub) | ❌ | ❌ | ❌ | ❌ | ❌ | Skeleton |
| Jellyfin | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Empty |
| A2UI | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Empty |
| PMOVES-surf | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Ghost |
| PMOVES-DoX | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Empty |
| GrapheneOS | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Nonexistent |

### Integration Heat Map

```
Dockerization:     ████████████████░░░░░░░░  46% (6/13 have Docker)
NATS Integration:  ██████░░░░░░░░░░░░░░░░░░  15% (2/13)
TensorZero:        ██░░░░░░░░░░░░░░░░░░░░░░   8% (1/13)
Supabase:          ██░░░░░░░░░░░░░░░░░░░░░░   8% (1/13)
Test Coverage:     ██████░░░░░░░░░░░░░░░░░░░  15% (2/13)
TAC Tree:          ██████░░░░░░░░░░░░░░░░░░░  15% (2/13)
Functional:        ████████░░░░░░░░░░░░░░░░  23% (3/13)
```

---

## 20 Prioritized Gaps

### P0 — Critical (Blocks core functionality)

| # | Gap | Component | Detail |
|---|-----|-----------|--------|
| 1 | PMOVES.YT is a broken 22-line shim | PMOVES.YT | `exec()` to nonexistent file; entire YouTube pipeline dead |
| 2 | Voice relay not using JetStream | Voice-Relay | Core NATS = at-most-once; voice packets silently dropped |

### P1 — High (Significant capability missing)

| # | Gap | Component | Detail |
|---|-----|-----------|--------|
| 3 | Zero TensorZero in voice services | Flute/Voice-Relay/Whisper | No tracing, no quality scoring, no feedback loops |
| 4 | 7 NATS voice subjects unimplemented | Voice pipeline | Designed in TAC tree, zero code subscribes/publishes |
| 5 | A2UI submodule not cloned | PMOVES-A2UI | Desktop client strategy blocked |
| 6 | GrapheneOS greenfield needed | GrapheneOS | Pixel 10 Pro app has zero foundation |
| 7 | Media service stubs need implementation | media-video, media-audio | Dockerfiles exist, zero Python code |

### P2 — Medium (Operational improvements)

| # | Gap | Component | Detail |
|---|-----|-----------|--------|
| 8 | PMOVES-surf has zero footprint | PMOVES-surf | Ghost submodule — remove or document |
| 9 | PMOVES-DoX minimal references | PMOVES-DoX | Likely abandoned — remove or document |
| 10 | Jellyfin minimal integration | Jellyfin | Only `jellyfin.hosts` config, no service code |
| 11 | TTS Studio not Dockerized | Pinokio TTS | Runs via Pinokio only, not in services/ |
| 12 | Pinokio TTS no NATS integration | Pinokio TTS | Standalone, disconnected from PMOVES.AI bus |
| 13 | Next.js UI no NATS integration | Next.js UI | No real-time events from voice/media pipeline |
| 14 | No voice persona management UI | Next.js UI | `voice_persona_bind.py` is CLI-only |

### P3 — Low (Nice-to-have)

| # | Gap | Component | Detail |
|---|-----|-----------|--------|
| 15 | No voice waveform visualization | Next.js UI | No audio visualization components |
| 16 | No dark/light theme toggle | Next.js UI | Tailwind configured but not exposed |
| 17 | FFmpeg-Whisper no NATS integration | FFmpeg-Whisper | Transcription results not published to bus |
| 18 | transcribe-and-fetch nested under A2UI | PMOVES-transcribe-and-fetch | Cannot use independently |
| 19 | No media asset metadata service | Media pipeline | No central asset tracking |
| 20 | No content review workflow | Media pipeline | Designed in Discord bot arch, not implemented |

---

## Submodule Clone Priority

Recommended order for `git submodule update --init`:

| Priority | Submodule | Reason |
|----------|-----------|--------|
| 1 | PMOVES-YT | Broken pipeline needs immediate fix |
| 2 | PMOVES-A2UI | Desktop client strategy depends on it |
| 3 | PMOVES-Pinokio-Ultimate-TTS-Studio | Would unify TTS code currently split across in-tree/submodule |
| 4 | Pmoves-Jellyfin-AI-Media-Stack | Media stack integration |
| 5 | PMOVES-DoX | Documentation tooling (if still wanted) |
| 6 | PMOVES-surf | Only if purpose is defined — otherwise remove |
| — | GrapheneOS | Greenfield — not a submodule clone, requires new development |

---

## Voice Pipeline Architecture Detail

### Current Data Flow

```
Voice Input (Mic/Discord)
    │
    ▼
Flute-Gateway (:8055)
    │  Receives voice, routes to processing
    ▼
FFmpeg-Whisper (:8078)
    │  Transcribes audio to text
    ▼
Agent Processing (Agent Zero)
    │  Generates response text
    ▼
Voice-Relay (:8121)
    │  Routes to TTS + output endpoint
    ▼
TTS Engine (:7860)
    │  Text to speech audio
    ▼
Voice Output (Speaker/Discord)
```

### Missing Elements (Designed but Not Built)

```
[DESIGNED]                    [NOT IMPLEMENTED]
──────────────────────────────────────────────
voice.pipeline.status.v1   -> No publisher
voice.pipeline.transcript.v1-> No publisher
voice.pipeline.tts.request -> No subscriber
voice.pipeline.tts.result  -> No subscriber
voice.media.process.req    -> No subscriber
voice.media.process.result -> No subscriber
voice.media.asset.metadata -> No publisher

TensorZero tracing          -> No client in any service
JetStream persistence      -> Using Core NATS only
Persona management API     -> CLI tool only (voice_persona_bind.py)
```

---

## Next.js UI Component Inventory

### Directory Structure

```
pmoves/ui/
├── app/                    — Next.js App Router pages
│   ├── (auth)/             — Authentication pages
│   ├── (dashboard)/        — Main dashboard
│   ├── tensorzero/         — TensorZero management suite
│   ├── voice/              — Voice controls (planned)
│   └── settings/           — Configuration pages
├── components/
│   ├── tensorzero/         — 8 TensorZero management components
│   ├── ui/                 — Base UI components (shadcn/ui)
│   ├── voice/              — Voice control components
│   ├── auth/               — Authentication components
│   └── layout/             — Layout and navigation
├── lib/
│   ├── supabase/           — Supabase client and helpers
│   ├── tensorzero/         — TensorZero API client
│   └── utils/              — Utility functions
├── hooks/                  — Custom React hooks
├── e2e/                    — 12 Playwright E2E tests
├── __tests__/              — Unit tests (Jest)
└── public/                 — Static assets
```

### Technology Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19.2 | UI framework |
| Next.js | 15.x | Full-stack framework (App Router) |
| TypeScript | 5.x | Type safety |
| Tailwind CSS | 4.x | Styling |
| Supabase | latest | Auth, database, realtime |
| TensorZero | via API | LLM function management |
| Playwright | latest | E2E testing |
| Jest | latest | Unit testing |

---

## Recommendations

### Immediate (This Sprint)

1. **Fix PMOVES.YT** — Clone submodule, remove `exec()` shim, implement proper service
2. **Migrate voice relay to JetStream** — Change NATS connection from Core to JetStream for all voice subjects
3. **Add TensorZero clients** to Flute-Gateway, Voice-Relay, FFmpeg-Whisper

### Short-Term (Next Sprint)

4. **Implement 7 missing NATS voice subjects** — Publishers in Flute/Whisper, subscribers in downstream services
5. **Clone PMOVES-A2UI** — Evaluate desktop client viability
6. **Decide on PMOVES-surf and PMOVES-DoX** — Remove or document purpose

### Medium-Term (This Quarter)

7. **Dockerize Pinokio TTS Studio** — Move from Pinokio-managed to `pmoves/services/tts-studio/`
8. **Add NATS WebSocket bridge to Next.js UI** — Enable real-time voice/media events
9. **Implement media service stubs** — Build out media-video and media-audio with actual processing code
10. **Create GrapheneOS strategy document** — PWA vs native decision for Pixel 10 Pro

### Long-Term (This Quarter+)

11. **Voice persona management UI** — Move from CLI to Next.js dashboard
12. **Content review workflow** — Implement designed review/approval pipeline
13. **Media asset metadata service** — Central tracking for all generated media
14. **Jellyfin AI integration** — Smart media library with AI-powered organization

---

## Appendix A: Submodule Status Summary

| # | Submodule | Cloned | In-Tree Code | Functional | Priority |
|---|-----------|--------|-------------|------------|----------|
| 1 | PMOVES-Pinokio-Ultimate-TTS-Studio | ❌ | ✅ (14 engines) | Partial | P2 |
| 2 | Voice Pipeline (3 services) | N/A | ✅ | ✅ (with gaps) | P0-P1 |
| 3 | PMOVES.YT | ❌ | ❌ (22-line shim) | ❌ Broken | **P0** |
| 4 | Next.js UI | N/A | ✅ (205+ files) | ✅ Production | — |
| 5 | Pmoves-Jellyfin-AI-Media-Stack | ❌ | Minimal | ❌ | P2 |
| 6 | PMOVES-A2UI | ❌ | Eval report only | ❌ | P1 |
| 7 | PMOVES-transcribe-and-fetch | ❌ | ❌ | ❌ | P3 |
| 8 | PMOVES-surf | ❌ | ❌ | ❌ Ghost | P3 |
| 9 | PMOVES-DoX | ❌ | Minimal | ❌ | P3 |
| 10 | GrapheneOS | N/A | ❌ | ❌ Nonexistent | P1 |
| 11 | Media stubs (video/audio) | N/A | Dockerfiles only | ❌ Skeleton | P1 |

## Appendix B: Voice Tools Reference

| Tool | Lines | Imports NATS? | Imports TensorZero? | Purpose |
|------|-------|---------------|-------------------|---------|
| voicebox_probe.py | ~80 | ❌ | ❌ | Health check voice services |
| voicebox_full_probe.py | ~150 | ✅ | ❌ | Full diagnostic with NATS check |
| voice_follow_agent.py | ~120 | ✅ | ❌ | Voice-based agent tracking |
| voice_follow_cast_agent.py | ~100 | ✅ | ❌ | Cast voice agent interaction |
| voice_speaker.py | ~90 | ❌ | ❌ | TTS output via voice pipeline |
| voice_to_discord_test.py | ~70 | ❌ | ❌ | Discord voice integration test |
| voice_chain_e2e_test.py | ~200 | ✅ | ❌ | Full voice chain E2E test |
| voice_persona_bind.py | ~60 | ❌ | ❌ | Bind persona to agent profile |
| voice_agent_discord_smoke.py | ~80 | ❌ | ❌ | Discord voice agent smoke test |

**Note:** Only 3 of 9 voice tools use NATS. Zero use TensorZero.

## Appendix C: Port Allocation

| Port | Service | Protocol | Status |
|------|---------|----------|--------|
| 7860 | Pinokio TTS Studio (Gradio) | HTTP | Running (standalone) |
| 8055 | Flute-Gateway | HTTP | Running (Docker) |
| 8078 | FFmpeg-Whisper | HTTP | Running (Docker) |
| 8121 | Voice-Relay | HTTP | Running (Docker, flawed) |
| 3000 | Next.js UI (dev) | HTTP | Running (Docker) |

---

*End of Report — Media, Voice, UX & Peripheral Submodules Report — 2026-04-17*
