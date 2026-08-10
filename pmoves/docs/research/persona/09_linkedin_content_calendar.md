# DARKXSIDE LinkedIn Content Calendar

> **Generated:** July 30, 2026 (link + claim re-verification: 2026-08-10)
> **Pipeline (planned):** ActivePieces → persona.pmoves.ai → pmoves.ai exhibits. **Not yet operable** — no publishing flow is exported to `pmoves/activepieces/flows/`, and `persona.pmoves.ai` did not resolve on 2026-08-10. See § Prerequisites before scheduling anything.
> **AI Playlist:** 2,028 videos crawled (`pmoves/docs/research/DARKXSIDE_PLAYLIST_ANALYSIS_2026-07-28.md`); 2,017 recorded as classified across 11 resonance domains (`docs/AGENT_TRAIL.md`). Crawled and classified are different buckets — do not use them interchangeably in post copy.

---

## Content → Resonance → Destination Map

Each LinkedIn post is *intended* to route to a specific pmoves.ai exhibit, with the persona room (`persona.pmoves.ai`) as the primary landing. **Every destination below is a target, not a verified live URL.** As of 2026-08-10 `persona.pmoves.ai` returns NXDOMAIN and no `pmoves.ai/*` exhibit path was reachable from outside the mesh. Confirm each destination serves publicly before it goes into a post.

| # | Artifact | Format | Primary Resonance | pmoves.ai Destination |
|---|----------|--------|-------------------|----------------------|
| 1 | "Build What You Need" origin story | LinkedIn post | ai-ml, community | `persona.pmoves.ai` → GitHub repo |
| 2 | "SOUL MOVES" track as origin myth | Featured/blog | media-creative | `pmoves.ai/embeds/beats-constellation/` |
| 3 | "5 Dimensions" framework | Carousel (5 slides) | science-philosophy | `persona.pmoves.ai` → 5 dimensions |
| 4 | "BPM-Prosodic Bridge" deep dive | LinkedIn article | ai-ml, energy | `pmoves.ai/embeds/beats-constellation/` (live FFT) |
| 5 | "The Sketch Is a Prototype" | Twitter/X thread | dev-tools | `pmoves.ai/hyperdim/?preset=beats_constellation.json` |
| 6 | "CHIT 37/37" milestone | LinkedIn post | security-privacy, infrastructure | `pmoves.ai/chit-tour/` (deploy unverified) |
| 7 | "From the Bronx" cultural identity | LinkedIn post | community | `persona.pmoves.ai` → Fordham Hill room |

---

## 11 Resonance Domains → Content Pipeline

The AI Playlist (2,028 crawled videos) is the intended input to auto-research that generates LinkedIn content.

> **Denominator warning — do not quote these counts publicly yet.** The per-domain counts below sum to exactly 1,000, not the 2,017 classified videos recorded in `docs/AGENT_TRAIL.md`. The `--stats` query in `pmoves/tools/yt_playlist_enrich.py` selects from `youtube_videos` with no `limit` and no pagination, so it is truncated by PostgREST's default 1,000-row cap. Read the table as a **1,000-video sample**: the *ordering* of domains is usable, the absolute counts are not. Paginate the stats query and regenerate before any of these figures appear in a LinkedIn post.

| Domain | Videos (of 1,000-row sample) | Content Angle | Exhibit Link |
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
| 5 | "CHIT 37/37" milestone (Artifact 6) | security-privacy | CHIT Tour | Draft ready (re-verify agent count against `pmoves/config/agent_registry.yaml` at post time — 98 on 2026-08-10) |
| 6 | "From the Bronx" (Artifact 7) | community | `persona.pmoves.ai` | Draft ready |
| 7 | "The Sketch Is a Prototype" (Artifact 5) | dev-tools | Hyperdim | Draft ready (X thread) |
| 8 | Auto-research from playlist domain | Rotating | Research artifact on `persona.pmoves.ai` | Generated weekly |

---

## ActivePieces Wiring (design — not built)

No flow is exported to `pmoves/activepieces/flows/` (that directory holds only a README), and `.github/workflows/activepieces-flow-search.yml` is a manual-dispatch read-only search — neither establishes a working LinkedIn publishing path. The flow, once built, should:
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

- [x] **CHIT Tour merged**: PR #2076 landed on main — `website/chit-tour/` is in the tree
- [ ] **CHIT Tour serving publicly**: `pmoves.ai/chit-tour/` did not return 200 from outside the mesh on 2026-08-10 (site root returned 403). Confirm the public deploy before linking it from a post.
- [ ] **persona.pmoves.ai live**: Traefik edge + DNS for the persona room (Phase 5 operator step). Verified NXDOMAIN on 2026-08-10 — this is the hard blocker for the whole calendar, since every artifact lands there.
- [ ] **Persona room content sync**: `pmoves/rooms/persona/persona.json` still advertises the pre-refresh counts (91 agents / 50 submodules / 5 rooms). Sync it to the values in `06_linkedin_profile.md`, then `make -C pmoves persona-render`, or the room will contradict the profile that links to it.
- [ ] **ActivePieces content queue**: Build and export the LinkedIn publishing flow to `pmoves/activepieces/flows/`, then wire the 7 artifacts into the AP scheduler
- [ ] **Playlist stats pagination**: Fix the unpaginated `--stats` query in `pmoves/tools/yt_playlist_enrich.py` so the 11-domain table reflects all classified videos rather than a 1,000-row page
- [ ] **Auto-research cron**: Weekly DeepResearch run on highest-video-count domain
