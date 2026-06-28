---
graphiti_mark: spec.voice-agents-multiengine.2026-06-26
branch: chore/omnivoice-4090-bringup
pr_numbers: [1885]
scope: Design + staged plan for multi-engine voice agents — unified voice-profile
  registry (Supabase), JuiceFS cross-node shared voice catalog, media→voice enrollment
  (pmoves-yt/jellyfin), web demo (talk/try/clone), enforceable rights/consent model.
  DESIGN ONLY — no implementation in this doc.
risks: voice-cloning rights/consent (hard gate required); JuiceFS POSIX-lock unproven;
  Ultimate-TTS RVC synthesize_cloned() is NotImplementedError (blocks the clone flow).
next_actions: operator answers §10 open questions → S1 (registry contract, 4090) → S3 (Try slice).
chit_artifact_path: n/a (design doc)
agent_signature: 4090-claude (synthesized from a 6-agent research fan-out)
---

# PMOVES.AI Multi-Engine Voice Agents — Design Doc

> **Provenance:** synthesized from a 5-dimension research fan-out (registry/multi-engine,
> JuiceFS storage, media enrollment, web-demo UX, rights/consent) + a synthesis pass —
> 6 agents, grounded in the live repo (`file:line` citations throughout). **Design only;**
> implementation is staged in §9 pending operator sign-off on §10.

## 1. Goal & Principles

Make agent and voice-agent expressiveness uniform across **all** flute-gateway TTS engines (OmniVoice, VibeVoice, Voicebox, Ultimate-TTS) by introducing one engine-agnostic **voice-profile contract** backed by Supabase (truth/routing) and JuiceFS (shared audio, MinIO interim), so any node can resolve, clone, and synthesize the same voice. New voices enroll **fast and durably** from media (`pmoves-yt` first, Jellyfin next) through reuse of existing `ffmpeg-whisper` extract/transcribe and a thin `voice:enroll` glue, gated by an enforceable rights/consent/provenance check (open-source/CC-BY only, per DARKXSIDE policy). A web demo lets anyone **talk / try / clone**. Principles: deterministic tools for grounding (extract, ASR-gate, hash) and models only for genuine synthesis; reuse existing services over new microservices; registry is the single discovery/routing layer while each engine keeps its native profile storage; consent is a hard gate, not a checkbox.

## 1a. Operator Decisions (2026-06-28) — authoritative

These resolve the §10 open questions and add binding architectural direction:

- **JuiceFS metadata engine — target = Postgres** (tier-data), not Redis. (Q1)
  ⚠️ *Current state:* the JuiceFS PoC compose defaults to **Redis** (`juicefs-redis`,
  `docker-compose.yml` `JUICEFS_META_URL=redis://juicefs-redis:6379/1`). Postgres is the
  **decided target**; migrating the JuiceFS metadata engine Redis→Postgres is a **Z890
  task** (gate it before the voice path relies on JuiceFS at S7 — until then the voice
  catalog uses the MinIO-interim path, §5).
- **Topology = host-or-standalone, hardware-impedance-matched** (Q2): every voice engine
  can run **standalone on a node** OR be **hosted by a capable node for others** (a small
  node taps a host instead of running the engine locally). Engine selection is by
  **purpose + available hardware/engines**, not a fixed default. Node→engine map:
  - **Heavy hosts (run larger / whole Ultimate-TTS, serve others):** SPARK, 5090, Z890, KNUCKLES.
  - **Light nodes (run small engine locally OR tap a host):** 4090, elder-melchor,
    missling-link, Jetsons — small/light engines only (OmniVoice, Voicebox, **Kokoro**).
  - Resolution: the registry profile names an `engine`; routing picks a **reachable
    instance** of that engine (local if present, else a hosting node over Tailscale
    MagicDNS) — `OMNIVOICE_URL`/per-engine URLs already normalize host targets.
- **Voice-design / control surface is ENGINE-SOURCED** (Q3): `instruct`/design params are
  **declared per engine** (engine capability/TAC), not a global freeform string. OmniVoice
  is *one* engine; an agent selects among many by purpose/hardware, and the design controls
  available come from that engine's declared surface. (Drives the capability matrix in §3
  becoming the source of truth for what each engine exposes.)
- **Demo posture (Q4/Q5) — no meter to be burned:**
  - **Public (pmoves.ai):** **pre-canned** voice-over-agent-trails — narrated chronicles of
    agent exploits / agent summaries / examples of voice agents. **Pre-rendered audio, not
    live synthesis** (zero per-visitor GPU cost).
  - **Live voice agents:** **private, on the Tailscale tailnet** — interested parties
    **join / sign up** to access; not open to the public internet.
  - **Any live public hosting** uses **light engines only (Kokoro / OmniVoice / small)** so a
    hosting Jetson/light node can't be overrun. `VOICE_CLONING_ENABLED=false` for public stays.
  - **Clone availability is mesh-gated (operator, 2026-06-28):** `VOICE_CLONING_ENABLED=false` on
    public ≠ "no clone." Voice cloning **IS available to registered nodes on the Tailscale mesh**
    (via Pinokio / MCP / A2A), authenticated and hard-gated by the consent/provenance model (§8).
    The **public website** keeps clone OFF and instead serves **pre-canned examples** + a
    **pass-through to the creator pipeline** that turns the live topology / agents / actions
    (real CHIT trails) into illustrative demos of PMOVES building itself. So: **clone on the mesh,
    demos on the web.** (The CHIT-trail-as-animated-story creator surface is its own roadmap thread —
    see `[[vision_chit_trail_creator_storytelling]]`.)
- **Voice RBAC (Q9) — post-launch via Supabase RLS** (operator, 2026-06-28): Wave-1 ships
  **creator-scoped ownership only** (a voice belongs to its `created_by`); full multi-tenant
  ownership/sharing ("who may clone Alice's voice?") lands later via RLS on `voice_profiles`,
  so S1-S8 are not blocked on it now.

**Pending operator confirmation — bind the mesh clone flow (clone is enabled on the tailnet):**
Q6 speaker-verify depth, Q7 multilingual representation, Q8 CHIT-signing for clone events,
Q10 async clone-training job location. These have design context already (Q7 ↔ the §3
`engine_specific`/`tags` language fields; Q8 ↔ the existing CHIT CGP publish in §8), so they're
*finalize*, not *design-from-scratch*. Public-website demos don't touch them (pre-canned); the
mesh clone path (S8) does — confirm before S8 lands.

## 2. Architecture Overview

```
                          ┌─────────────────────────────────────────────┐
   Web Demo (A2UI/Next)   │  flute-gateway :8055  (routing + registry)    │
   talk / try / clone ───▶│  /v1/voice/agent (WS duplex)                  │
                          │  /v1/voice/synthesize, /stream/tts           │
                          │  /v1/voice/registry, /try, /clone/*  (new)   │
                          │  persona_selector → voice_profiles lookup    │
                          └───────┬───────────────┬──────────────┬───────┘
                                  │ engine routing │              │ registry read (cache+TTL+NATS)
                  ┌───────────────┼────────┬───────┴────┐         ▼
                  ▼               ▼        ▼            ▼   Supabase pmoves_core.voice_profiles
            OmniVoice :8002   VibeVoice  Voicebox  Ultimate-TTS   (+ voice_cloning_provenance)
            (clone+design)    (stream)   (clone)   (14 eng,F5)
                  │ ref_audio                                     ▲ enroll upsert
                  ▼ catalog dir = JuiceFS mount                   │
        ┌──────────────────────────────────────────┐    voice:enroll glue
        │ JuiceFS /mnt/juicefs/voices/  (MinIO now) │◀── (creator-operator /voice/enroll)
        │  catalogs/default | enrolled/<user> | yt/ │      ▲
        └──────────────────────────────────────────┘      │ fetch+extract+ASR+gate
                                                   pmoves-yt / jellyfin-bridge → ffmpeg-whisper
```

**Data flow (synthesize):** request (`persona_id`/`voice`/`intent`) → `flute-gateway` resolves voice → if `voice` slug present, registry returns `engine` + `engine_specific` params → provider call → audio out + CHIT CGP event (`tokenism.geometry.event.v1` / `geometry.cgp.v1`) carrying provenance meta.

**Data flow (enroll):** media source → fetch (pmoves-yt/jellyfin-bridge) → `ffmpeg_extract_audio()` 24 kHz mono → optional `ffmpeg-whisper` ref_text → rights/consent gate → write WAV to JuiceFS/MinIO `voices/` → upsert `voice_profiles` + `voice_cloning_provenance` → publish `voice.enrollment.completed.v1`.

## 3. Unified Voice-Profile Contract + Capability Matrix

**`voice_profile` (one row = one resolvable voice):**
- Identity: `name` (slug, `^[a-zA-Z0-9_-]{3,64}$`, unique), `display_name`, `description`, `tags[]`, `created_by`, `created_at`/`updated_at`, `deleted_at`, `is_active`.
- Routing: `engine` (target), `engine_specific` (JSONB, per-engine param block).
- Media: `ref_audio_path` (`juicefs://pmoves-voices/<name>.wav`), `sample_path`, `sample_rate_hz` (24000), `audio_duration_sec`.
- Provenance (mirror/FK to `voice_cloning_provenance`): `provenance`, `rights_basis`, `cloned_from`, `clone_method`.

**`engine_specific` shapes:** `omnivoice{ref_audio, instruct, ref_text}` · `voicebox{profile_id, voice_type, language}` · `ultimate_tts{primary_engine, fallback_engines[], <engine>_voice}` · `vibevoice{voice_preset}`.

**`grounding` JSONB — a CONTRACT (not illustrative).** Keys resolve to the real substrate PKs; `/validate` (S1b) enforces the shape:
```
{ "persona_ids": uuid[]          → v5_12 pmoves_core.personas.persona_id,
  "consciousness_theory_id": text → v5_15 pmoves_core.consciousness_theories.id,
  "paradigm": text,
  "paradigm_proponent_ids": id[]  → NEEDS a backing table or a named resolver (none yet),
  "proponents": [{name, weight, ref_audio}], "blend": "weighted" }
```
Use `consciousness_theory_id` (NOT `consciousness_shape` — v5_15 has no "shape" column). A voice grounded in a blend of paradigm proponents resolves through this; grounding is the cross-lane spine (see §4a), not a voice-only column.

**Capability matrix** (drives realtime vs batch routing; persist as config YAML or table):

| Engine | clone | design | streaming | langs | native profile store | role |
|---|---|---|---|---|---|---|
| OmniVoice | ✅ ref_audio+ref_text | ✅ instruct | ❌ batch | en | catalog dir (JuiceFS) | default clone/design (batch) |
| Voicebox | ✅ POST samples | ✅ design_prompt | ❌ poll | en/multi | Voicebox DB (UUID) | persisted clone profiles |
| Ultimate-TTS | ✅ F5/Fish zero-shot | ❌ | ✅ SSE (Higgs/Chatterbox) | en/multi | none (preset id) | RVC clone synthesis + stream |
| VibeVoice | ❌ | ❌ | ✅ WS | en | preset only | realtime preset agent |

**Routing rule:** realtime `/v1/voice/agent` → streaming-capable (VibeVoice, Ultimate-TTS); clone/design batch (`/synthesize`, `/try`) → OmniVoice/Voicebox; cloned-voice synthesis → Ultimate-TTS RVC.

## 4. Registry Decision (concrete)

**Decision: Supabase `pmoves_core.voice_profiles` is the source of truth + routing layer; engines keep native profile storage; JuiceFS holds audio.** Reject node-local file catalog (inconsistent across SPARK/4090/5090/Z890). Reject collapsing into `cast_voice_profiles` (it is device/group-scoped, not engine-agnostic — `cast_tts_persistence.sql:7-17`).

- **New table** `pmoves_core.voice_profiles` (schema §3) via idempotent migration `pmoves/db/v5_16_voice_catalog.sql`. Keep `voice_persona` and `cast_voice_profiles` as-is; `persona_selector.py` resolves persona → `voice_profile` with **fallback** to legacy `voice_persona` (2-week deprecation window for invalid `engine_specific`).
- **flute-gateway consistency:** preload registry in `main.py` lifespan into an in-process cache; refresh on 5-min TTL; invalidate on NATS `voice.registry.update.v1`. `select_provider_and_params()` priority: explicit `voice` slug → registry; else `persona_id` → `resolve_persona_engine()` (unchanged, `persona_selector.py:71-154`); else `intent`; else `DEFAULT_VOICE_PROVIDER` (omnivoice, PR #1885).
- **Voicebox bootstrap:** on empty Voicebox (`VoiceboxNoProfileError`), auto-create a preset (Kokoro `af_bella`), cache its UUID into a profile row.
- **New endpoints:** `GET /v1/voice/profiles` (list/filter by tag/engine/rights), `GET /v1/voice/profiles/{name}`, `POST /v1/voice/profiles`, `POST /v1/voice/profiles/{name}/validate` (checks requested params against capability matrix).
- **RLS uses dependency-free, repo-standard accessors** — `auth.uid()` (owner/sub; Supabase built-in, used in `channel_monitor_tables.sql`) and **`TO service_role`** (Postgres-role-targeted policies for service access; `service_catalog.sql:73`). **Do NOT use** the PostgREST-9.0-removed `request.jwt.claim.*` GUCs (resolve empty → dead RLS) **nor `jwt_claim_role()`** (NOT defined anywhere in repo SQL — using it aborts `CREATE POLICY`). Applied in #1890 (v5_16) + #1897.

## 4a. Convergence — Voice as a Discoverable Capability (two planes, one join key)

The voice-agent pair-review (#1890 ↔ SPARK #1893 agent_registry MCP/A2A discovery ↔ #1894 room MCP apps/bindings) found three lanes picking **divergent idioms** for "register a capability": voice = Postgres table + closed engine enum (#1890); MCP/A2A servers = open YAML + env (#1893); rooms = skill-name bindings (#1894). Voice is therefore **not discoverable** via `agent_registry`, and **grounding lives only on a voice row** — an agent's grounded identity (#1890) and its discoverable capabilities (#1893/#1894) sit in disjoint substrates with no join key.

**Principle — two planes, one join key.** `voice_profiles` stays the *truth + routing* plane (rich engine_specific, RLS, media). Add a thin *discovery shim* so voice is reachable through the same `agent_registry → room` plane as every other capability. Don't collapse one into the other; bridge them.

1. **Discovery plane (#1893):** register voice as an `mcp_servers` entry — `name: pmoves-voice-mcp`, `class: flute_gateway`, `action_namespace: mcp.v1.voice`, `capabilities: [voice, tts, voice-select, clone]`, `endpoint_env: PMOVES_VOICE_MCP_ENDPOINT`, `rooms: ["5090-voice.room.studio"]`, and a `resolves: {registry: supabase, table: pmoves_core.voice_profiles, by: name}` join to the truth plane.
2. **Room plane (#1894):** add `app_id: mcp-voice` + a `skill_binding` (`intent:[voice,tts]`, `context.sources:[agent-registry, persona]`) in `5090-voice.room.studio`; runtime resolves a `voice_profiles` row by `name` slug.
3. **Shared capability vocabulary** (single union list incl. `voice`/`tts`); room app `capabilities` *reference* the registry list, validator cross-checks (kills the double source of truth).
4. **Lifecycle-key policy:** `status` (planned/active = *deployment* lifecycle) is shared across the DB + YAML registries (voice `status` derived from `is_active`); `evolution_stage` (agent *maturity*) is orthogonal — not a synonym.
5. **Naming map (one documented chain):** `registry_key (snake)` ↔ `name/provider (kebab)` ↔ `action_namespace (mcp.v1.<x>)` ↔ `voice name (slug)`.
6. **Grounding becomes the shared spine:** mark `hirag`/`cipher` mcp_servers with `grounding_source: true` so a discovering agent knows where to retrieve startup grounding. Resolution becomes one path: **room discovery → agent-registry (grounding_source) → voice_profiles.grounding → personas(v5_12) / consciousness_theories(v5_15) / paradigm-proponents.**

This is delivered as **S1c** (§9) — a cross-lane PR after SPARK #1893/#1894 land; none of the three current PRs block on it.

## 5. JuiceFS Cross-Node Voice Storage

**Target (Mode B, POSIX, zero-copy):** JuiceFS mounted `/mnt/juicefs` on every node; `OMNIVOICE_REFERENCE_VOICE_DIR=/voices` bind-mounted from `/mnt/juicefs/voices`. Layout:
```
/mnt/juicefs/voices/{catalogs/default, enrolled/<user>, youtube/<channel>}
```
Enrollment writes temp-file then atomic `rename` into `enrolled/`; cross-node mutual exclusion via NATS `voice.enroll.lock.request/grant` (POSIX `fcntl` across FUSE is unproven — test before relying). Metadata engine = Redis or Postgres (Z890 decides, `AGNOTE4482PHI.t1:1058`). New-voice visibility = Redis cache TTL (~30 s); if agents need <5 s, add an explicit catalog-refresh trigger off `voice.enrollment.completed.v1`.

**Interim (ships now, MinIO):** dedicated `voices/` bucket (`catalogs/default | enrolled/<user> | youtube/<channel>`), object versioning on for concurrent-write safety. OmniVoice catalog dir = host FUSE mount (`s3fs`) or NFS re-export bound read-only into the container. Single env switch `S3_ENDPOINT` (minio:9000 → juicefs-gateway:9000) with fallback. Cross-node reach via Tailscale MagicDNS (`OMNIVOICE_URL` → `pmoves-<node>.<tailnet>.ts.net:8002`); `127.0.0.1` already normalized to `host.docker.internal` (`main.py:183`).

**Z890 coordination (gates):** JuiceFS Phase-1 PoC stabilization (`docker-compose.juicefs.yml`, PR #1865); confirm S3-gateway `presign_post`/`presigned_get` parity before consumers cut over (`MEDIA_DATA_ARCHITECTURE_PLAN.md:14`); Tailscale ACL must list `tag:storage` in `tagOwners` before tagged auth keys (`:20`); mirror final MinIO image to GHCR before Feb 2027 as EOL contingency.

## 6. Media Enrollment Workflow (`voice:enroll`)

**Endpoint:** `POST /voice/enroll` on **creator-operator** (Option A — minimal new code, ≤350 LOC `voice_enrollment.py`; no new microservice). Skill `/voice:enroll` and n8n are post-launch wrappers.

**Input:** `{source: "yt-url"|"jellyfin:<item_id>"|"local:<path>", source_url?, time_range?{start_sec,end_sec}, voice_name, tags[], rights_basis, consent_method, ref_text_override?, force?}`.

**Steps (reuse-first):**
1. **Fetch** — `pmoves-yt` (yt-dlp, first) → staging; `jellyfin-bridge /api/items/{id}/download` (next); `local:` whitelisted to `/mnt/juicefs/incoming` only.
2. **Rights/consent gate (§8)** — block non-commercial / unconsented before any compute.
3. **Extract** — `ffmpeg_extract_audio()` (`ffmpeg-whisper/server.py:373-386`) → 24 kHz mono WAV; apply `time_range` trim; prefer single-speaker segment via diarization, else highest-confidence segment.
4. **ref_text** — use `ref_text_override` (validate len>10, no null bytes) else `ffmpeg-whisper /transcribe_file`; ASR-confidence gate >0.85, voice-activity >2 s.
5. **Store** — write WAV to `voices/{enrolled|youtube}/<name>.wav` (JuiceFS/MinIO); name collision = 409 unless `force`.
6. **Register** — upsert `voice_profiles` + `voice_cloning_provenance` (PostgREST `Prefer: resolution=merge-duplicates`, cast-tts-gateway pattern).
7. **Announce** — publish `voice.enrollment.completed.v1` (register subject in `.claude/context/nats-subjects.md`) → triggers registry refresh + persona-bind discoverability.

**New glue only:** `voice_enrollment.py`, a `router.py` route, the SQL migration, two NATS subjects. Everything else is existing services. Long clips → async 202 + status poll; sync OK for <60 s.

## 7. Web-Demo Flows + API Surface + Consent UX

**FLOW A — Talk** (reuse `/v1/voice/agent` WS, `main.py:1302-1367`): browser mic → PCM16 24 kHz binary frames; receives `transcription`/`llm_text`/audio. New work is frontend (`pmoves/ui/app/demo/voice-agent`) + extend handshake to accept `{persona_id, voice_id}`. Per-connection rate-limit inside the WS transport (frames/sec).

**FLOW B — Try** (new, thin): `GET /v1/voice/registry` (from `voice_profiles`, with sample preview) + `POST /v1/voice/try {text, voice_id}` → routes to OmniVoice `/synthesize` with `ref_audio`. No training.

**FLOW C — Clone:** record ~10 s → `POST /v1/voice/clone/register` (multipart) → `VoiceCloningProvider.register_voice_sample()` → status poll `GET /v1/voice/clone/status/{persona_id}` → on `completed`, voice appears under "My Voices". **Blocker:** `synthesize_cloned()` is `NotImplementedError` (`cloning.py:451`) — must wire Ultimate-TTS RVC synthesis to finish C.

**Consent UX:** consent gate is mandatory before any flow; for clone, record consent audio, STT-verify (speaker-match optional/Wave 2), store immutable artifact, explicit data-retention + GDPR/CCPA language. Rate limits: talk 5 concurrent/IP, try 50/min/IP, clone-register 3/day/user + 50 pending system-wide, status poll 1/10 s.

## 8. Rights / Consent / Provenance Model (enforceable)

**Table `voice_cloning_provenance`** (FK `voice_persona_id`): `source_type` (YOUTUBE|MOVIE|OWNED_RECORDING|SYNTHETIC|CHARACTER_OWNED), `source_url`, `source_timestamp_start/end`, `source_title`, **`rights_basis`** (OWNED|LICENSED|CONSENTED|PUBLIC_DOMAIN|CHARACTER_OWNED), `consent_method`, `consent_date`, `consent_artifact_uri`, `capturer_identity`, `attribution_required`, `notes`, audit fields. Unique on `(voice_persona_id, source_url, source_timestamp_start)`.

**Enforcement (hard gate, two places):**
- **Enrollment** — no silent enrollment from URLs; license check mirrors the image/music model gate (`feedback_open_source_only`): non-commercial (CC-BY-NC) source → **BLOCK**. CONSENTED requires a recorded consent artifact; CHARACTER_OWNED/LICENSED require uploaded agreement (202 until attached).
- **Synthesis** — `OmniVoiceProvider.synthesize()` looks up provenance by voice slug; missing record → reject; `CHARACTER_OWNED` gated to active character context (NATS-backed authorization, not request flags); `is_active=false` (revoked) → reject.

**Attribution:** cloned-voice synthesis injects minimal `voice_provenance{voice_persona_id, rights_basis, consent_date, capturer_id, attribution_url}` into CHIT CGP `meta` (`_publish_chit_voice_event`, `main.py:255-342`) riding `tokenism.geometry.event.v1`/`geometry.cgp.v1`; full record stays in Supabase to avoid CGP bloat. Attribution is **historical** (proves consent-at-synthesis); consumers check revocation at read-time. Default `VOICE_CLONING_ENABLED=false` for public deploy until operator opt-in.

## 9. Staged Delivery Plan (PR-sized units)

| Stage | Scope | Lane | Built / New |
|---|---|---|---|
| **S1 — Registry contract** | `voice_profiles` table + migration `v5_16`; flute-gateway lifespan preload + cache + `select_provider_and_params`; `GET/POST /v1/voice/profiles`, `/validate` | **4090** | `cast_tts_persistence`/`persona_selector` exist; table+endpoints new |
| **S1-gate — migration applier** | confirm `pmoves/db/v5_16` (and v5_15) actually apply: `apply_migrations_docker.sh` globs only `pmoves/supabase/migrations/*.sql` → move v5_16 there OR wire the `pmoves/db` lexical-order applier (after v5_13 grants). **Gates #1890 applying in standard deploys.** | **Z890-DB** | runner exists; path-wire new |
| **S1c — Voice discovery unification** (§4a) | register voice in `agent_registry` (`mcp.v1.voice`, caps `voice/tts`) + `5090-voice.room.studio` binding; `grounding_source:true` on hirag/cipher; shared capability vocab; validator cross-checks (`app_id→apps[]`, registry↔manifest); naming-map doc | **cross-lane** (4090 + SPARK) | after #1893/#1894 land; none block on it |
| **S2 — Capability matrix + routing** | capability YAML/table; realtime-vs-batch routing; Voicebox bootstrap preset | **4090** | providers exist; matrix+routing new |
| **S3 — Vertical slice: Try** | enable `OMNIVOICE_REFERENCE_VOICE_DIR` (3-5 seed voices, MinIO interim), `GET /registry`, `POST /try`, demo Try page + consent checkbox + basic rate-limit | **4090** | OmniVoice `/synthesize` exists; registry/try/UI new |
| **S4 — Talk demo** | frontend WS duplex page; handshake `{persona_id, voice_id}`; per-conn rate-limit | **4090** | `/v1/voice/agent` exists; UI + handshake new |
| **S5 — Provenance gate** | `voice_cloning_provenance` table; enrollment license/consent gate; synthesis gate; CGP meta attribution | **codex** (Three-Body via field-brief) | CHIT publish exists; tables/gates new |
| **S6 — Media enroll (yt)** | creator-operator `/voice/enroll` + `voice_enrollment.py`; pmoves-yt fetch; ffmpeg-whisper reuse; `voice.enrollment.completed.v1`; subject doc | **codex** | fetch/extract/ASR exist; glue+subjects new |
| **S7 — JuiceFS pilot** | mount `/mnt/juicefs` on 4090; migrate `voices/`; repoint catalog dir; cross-node enroll→synthesize smoke (enroll 4090 / read 5090) | **Z890-JuiceFS** | PoC exists; mount+migrate+S3 parity new |
| **S8 — Clone flow** | finish `synthesize_cloned()` ↔ Ultimate-TTS RVC; browser record/poll UI; "My Voices" | **5090** (GPU/RVC) | provider skeleton exists; RVC synth + UI new |
| **S9 — Multi-node rollout** | mount remaining nodes; consistency <30 s; decommission MinIO `voices/` | **Z890-JuiceFS** | — |
| **S10 — Jellyfin enroll + polish** | jellyfin-bridge source path; auto-enroll dialogue; speaker-verify (Pyannote); revocation/audit dashboard | **5090 + codex** | bridge exists; enroll path + verify new |

Critical path to first user value: **S1 → S3** (Try, no clone). Talk (S4) parallels. Clone (S8) depends on S5 (gate) + S2 + RVC wiring.

## 10. Open Questions for the Operator

**Q1–Q5 RESOLVED 2026-06-28 — see §1a Operator Decisions.**

1. ✅ **JuiceFS metadata engine** → **target Postgres** (tier-data). *Current PoC defaults to Redis (`juicefs-redis`); Redis→Postgres migration is a Z890 task, gated before the voice path uses JuiceFS at S7 (MinIO-interim until then).*
2. ✅ **Topology** → **host-or-standalone, hardware-impedance-matched** (heavy hosts SPARK/5090/Z890/KNUCKLES serve or run full Ultimate-TTS; light nodes 4090/elder-melchor/missling-link/Jetsons run small engines or tap a host). Not a single fixed instance.
3. ⬜ **Ultimate-TTS RVC synthesis API signature** — still needed to unblock S8 `synthesize_cloned()` (`{rvc_model, rvc_index, text} → audio`?).
4. ✅ **Voice-design surface** → **engine-sourced** (per-engine declared capability/TAC), not a global freeform string. Agents select engine by purpose/hardware; design controls come from that engine.
5. ✅ **Demo posture** → **public = pre-canned voice-over-agent-trails** (no live synthesis); **live voice agents = private Tailscale, join/sign-up**; light engines (Kokoro/OmniVoice) only for any live public hosting; `VOICE_CLONING_ENABLED=false` public stays.
6. ⬜ **Speaker-verification depth** — ship Wave-1 clone with consent-audio only, or block OWNED enrollment on Pyannote liveness from day one (deepfake-spoof risk)?
7. ✅ **Multilingual + translation** (2026-06-28) → **yes**: a profile carries `tags=[multilingual,…]` with per-request **language control** AND a **translation** capability (translate source text before synthesis). Engine language support comes from the engine-sourced capability surface (§1a/Q4).
8. ✅ **CHIT signing for clone events** (2026-06-28) → **yes, if clone is kept** — clone training + cloned synthesis are CHIT-signed like normal synthesis (provenance rides CGP `meta`, §8).
9. ✅ **Voice RBAC** (2026-06-28) → **yes, via Supabase** — multi-tenant ownership/sharing enforced with **Supabase RLS** on `voice_profiles`/`voice_cloning_provenance` (owner + grant model).
10. ⬜ **Where does the async clone-training job live** — flute-gateway `voice.training.request.v1`, creator-operator, or n8n with approval gates? (decide at S8)

> **Still open (later-stage, non-blocking for S1–S4):** Q3 (Ultimate-TTS RVC API sig → S8), Q6 (speaker-verify depth → clone wave), Q10 (clone-job home → S8).