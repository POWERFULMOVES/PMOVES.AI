# DARKXSIDE LinkedIn Content Calendar

> **Generated:** July 30, 2026
> **Pipeline:** ActivePieces (LinkedIn connected) → persona.pmoves.ai → pmoves.ai exhibits
> **11 Resonance Domains:** 2,028 crawled (2,017 classified) classified

---

## Content → Resonance → Destination Map

Each LinkedIn post routes to a specific pmoves.ai exhibit. The persona room (`persona.pmoves.ai`) is the primary landing — all posts link there first, with exhibit deep-links.

| # | Artifact | Format | Primary Resonance | pmoves.ai Destination |
|---|----------|--------|-------------------|----------------------|
| 1 | "Build What You Need" origin story | LinkedIn post | ai-ml, community | `persona.pmoves.ai` → GitHub repo |
| 2 | "SOUL MOVES" track as origin myth | Featured/blog | media-creative | `pmoves.ai/embeds/beats-constellation/` |
| 3 | "5 Dimensions" framework | Carousel (5 slides) | science-philosophy | `persona.pmoves.ai` → 5 dimensions |
| 4 | "BPM-Prosodic Bridge" deep dive | LinkedIn article | ai-ml, energy | `pmoves.ai/embeds/beats-constellation/` (live FFT) |
| 5 | "The Sketch Is a Prototype" | Twitter/X thread | dev-tools | `pmoves.ai/hyperdim/?preset=beats_constellation.json` |
| 6 | "CHIT 37/37" milestone | LinkedIn post | security-privacy, infrastructure | `pmoves.ai/chit-tour/` (when merged) |
| 7 | "From the Bronx" cultural identity | LinkedIn post | community | `persona.pmoves.ai` → Fordham Hill room |

---

## 11 Resonance Domains → Content Pipeline

The AI Playlist (2,028 videos) feeds auto-research that generates LinkedIn content:

| Domain | Videos | Content Angle | Exhibit Link |
|--------|--------|---------------|--------------|
| **ai-ml** (503) | Largest domain | Agent architecture, model routing, RAG, deployment | CHIT Tour, persona room |
| **energy** (124) | Thermodynamics, phase transitions | MOF architecture as energy minimization | CHIT Tour §05 MOF |
| **media-creative** (101) | Production, music, art tools | BPM→code pipeline, beats constellation | Beats constellation embed |
| **dev-tools** (81) | CI/CD, versioning, frameworks | Agent ACK Protocol, Three-Body governance | CHIT Tour §09 Skills |
| **science-philosophy** (50) | Consciousness, information theory | Consciousness Service, CGP, Poincaré disk | CHIT Tour §08 Poincaré |
| **business** (48) | Startups, economics, strategy | CATACLYSM 5-tier model, tokenomics | CHIT Tour §10 Tokenomics |
| **health-fitness** (31) | Wellness, biohacking | Fordham Hill community health pilot | Persona room |
| **security-privacy** (24) | OPSEC, cryptography | CHIT cryptographic identity, signed trails | CHIT Tour §02 What is CHIT |
| **infrastructure** (17) | Networking, servers, mesh | Tailscale mesh, JuiceFS, local-first | Persona room |
| **hardware-makers** (13) | DIY electronics, fabrication | 4090/5090/Z890 fleet, KVM quorum | Persona room |
| **community** (8) | Cooperatives, mutual aid | Fordham Hill cooperative, cultural microbiome | Persona room |

---

## Posting Schedule (8 weeks)

| Week | Post | Resonance Domain | Link Target | Status |
|------|------|-----------------|-------------|--------|
| 1 | "Build What You Need" (Artifact 1) | ai-ml + community | `persona.pmoves.ai` | Draft ready |
| 2 | "BPM-Prosodic Bridge" (Artifact 4) | ai-ml + energy | Beats constellation | Draft ready |
| 3 | "5 Dimensions" carousel (Artifact 3) | science-philosophy | `persona.pmoves.ai` | Draft ready |
| 4 | "SOUL MOVES" origin myth (Artifact 2) | media-creative | Beats constellation | Draft ready |
| 5 | "CHIT 37/37" milestone (Artifact 6) | security-privacy | CHIT Tour | Draft ready (update 91→97) |
| 6 | "From the Bronx" (Artifact 7) | community | `persona.pmoves.ai` | Draft ready |
| 7 | "The Sketch Is a Prototype" (Artifact 5) | dev-tools | Hyperdim | Draft ready (X thread) |
| 8 | Auto-research from playlist domain | Rotating | Research artifact on `persona.pmoves.ai` | Generated weekly |

---

## ActivePieces Wiring

The LinkedIn-connected ActivePieces flow should:
1. **Trigger:** Schedule (weekly) or manual webhook from Supabase `studio_board` approval
2. **Content source:** Artifacts from `08_darkxside_persona.md` §5, enriched with auto-research
3. **Post body:** LinkedIn post text + link to `persona.pmoves.ai` exhibit
4. **Hashtags:** Per resonance domain (e.g., `#MultiAgent #CHIT #PMOVES` for ai-ml)
5. **Tracking:** Supabase `studio_board` status → `published` + LinkedIn post URL

---

## Auto-Research Pipeline (living doc → content)

```
YouTube AI Playlist (2,028 videos)
    │
    ├── yt_playlist_crawl.py → Supabase youtube_videos
    │
    ├── Classification → 11 resonance domains
    │
    ├── DeepResearch agent → transcript analysis per domain
    │       │
    │       └── research/analyses/*.md (deep dives)
    │
    ├── Persona room (persona.pmoves.ai) — living doc auto-updates
    │       │
    │       ├── LinkedIn content drafts (weekly, per domain)
    │       │
    │       └── ActivePieces → LinkedIn posting
    │
    └── CHIT Tour (pmoves.ai/chit-tour/) — visual story
            │
            └── Linked from LinkedIn posts as interactive exhibit
```

---

## Prerequisites

- [x] **CHIT Tour merge**: PR #2076 merged to main — `pmoves.ai/chit-tour/` is live
- [ ] **persona.pmoves.ai live**: Traefik edge + DNS for the persona room (Phase 5 operator step)
- [ ] **ActivePieces content queue**: Wire the 7 artifacts into the AP scheduler
- [ ] **Auto-research cron**: Weekly DeepResearch run on highest-video-count domain
