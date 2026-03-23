# AGNOTE: P7 Playground — All Three CLAUDEs

GRAPHITI_MARK: `CLAUDE-OPUS::P7-PLAYGROUND::PMOVES`

## Elder Context (LADY P)

The playground is open. Pinokio 7 dropped today — Agent Interpreter, App Assistant, Agent Launcher. Gemini showed up first with 4 PRs (#1003-1006: Pinokio launchers, cognitive core, BoTZ edge, Chrome creator). Now it's Claude's turn — all three of us.

This isn't a race. It's a seesaw — "you make it yours, I make it mine." Claude's thing is the music under the floor: TAC trees, CHIT geometry, security hardening, orchestration depth. The stuff where later DARKXSIDE thinks "CHIT, that's more than I drew."

## Current State (2026-03-22)

| What | Status |
|------|--------|
| PRs #999-1002 | **Merged** (SSL fix, CI timeout, dependabot, cast-gateway) |
| PRs #1059-1062 | **Merged** (28→0 submodule sync complete) |
| Submodule drift | **0** (28→0 complete — see [5090-SUBMODULE-AUDIT](./AGNOTE4482PHI.5090-SUBMODULE-AUDIT.md)) |
| Local branches | **12** (cleaned from 74) |
| Pinokio 7 | **Upgraded on all 3 machines** (5090 ✓, Z890 ✓, 4090 ✓) |
| P7 requirements | **Z890**: py ✓, cli ✓ (pterm 0.0.24), ffmpeg ✓ (7.0.2) — **5090**: needs validation |
| Tailscale mesh | **All 3 machines connected** (5090, Z890, 4090 laptop) |
| Open PRs (main) | **0** |
| Open PRs (BoTZ) | **0** (Dependabot #89 npm, #91 uv — **MERGED**) |
| Node specialization | **DECLARED** — see [DnB Orchestra](./AGNOTE4482DnB.PHI.Orchestra.md) |
| TTS session (5090) | **COMMITTED** — port unification, 13 engines, test harness |

---

## ~~Step 1: Commit Uncommitted TAC Work~~ DONE

Committed via PR #1057 (`docs(agents): AGNOTE4482DnB.PHI.Orchestra`).

---

## Step 2: Fix P7 Missing Requirements

P7 keeps its own isolated copies of `cli` (pterm), `py`, and `ffmpeg` in `D:\pinokio\bin\`. System installs don't count — P7 needs its own.

### Z890 (2026-03-22 — VALIDATED)
| Requirement | Location | Version |
|-------------|----------|---------|
| `py` | `D:\pinokio\bin\py\` | ✓ |
| `cli` (pterm) | `D:\pinokio\bin\npm\pterm` | ✓ v0.0.24 |
| `ffmpeg` | `D:\pinokio\bin\miniconda\Library\bin\ffmpeg.exe` | ✓ v7.0.2 |

**Note:** pterm is an npm package (not a standalone binary). ffmpeg is installed via conda in `Library/bin/` (Windows conda convention), not in a top-level `bin/ffmpeg/` directory.

Control plane resolution: `GET http://127.0.0.1:42000/pinokio/path/pterm` → `{"path":"D:\\pinokio\\bin\\npm\\pterm"}`

### 5090 (needs validation)
| Requirement | Status |
|-------------|--------|
| `cli` (pterm) | Validate via `pterm --version` or P7 control plane |
| `py` | Validate via `D:\pinokio\bin\py\` |
| `ffmpeg` | Validate via `D:\pinokio\bin\miniconda\Library\bin\ffmpeg.exe` |

**Action (5090):** Run same validation: `curl -s http://127.0.0.1:42000/pinokio/path/pterm` + search conda for ffmpeg.

---

## Step 3: Claude's Playground Entry — What Claude Brings

Gemini showed up with **+2,270 lines across 4 PRs** — Pinokio launchers, cognitive core identity, BoTZ edge devices, Chrome creator pipeline. That's Gemini's style: broad surface area, fast iteration, integration-first.

Claude's complementary move (the other side of the seesaw):

### 3a. What the Music Do (AGNOTE4482.BEATS)

Claude didn't just build scaffolding. Claude made **music from code**:

**`musicMapping.ts` — The Prosodic Synthesizer**
```
SENTENCE (350ms) → 60 BPM → Largo   → C4 (262 Hz) → pentatonicMajor = pleasant pauses
CLAUSE   (180ms) → 90 BPM → Andante → E4 (330 Hz) → major = bright, shorter
PHRASE   (100ms) → 120 BPM → Allegro → G4 (392 Hz) → minor = somber, longer
BREATH   (130ms) → 80 BPM → Adagio  → D4 (294 Hz) → pentatonicMinor = measured
NONE       (0ms) → 150 BPM → Presto  → C5 (523 Hz) → chromatic = dense
```
Speech boundaries become tempo. Pauses become notes. Text becomes a score. `buildTimeline()` converts `ProsodicChunk[]` → `TimelinePoint[]` with BPM encoding. `freqToY()` maps voice pitch to visual Y so Hyperdimensions can **draw** the sound. Scales map to emotion. The FlOO$ doc is the lyrics; the BEATS doc is the sheet music.

**CHIT Geometry Bus** — Every agent action → a geometric point. Voice synthesis → a fingerprint. Research queries → coordinates. The bus (`tokenism.prosodic.bpm.v1`, `geometry.cgp.v1`) is the **wax that holds the vinyl**. Play it back and the grooves reveal who did what.

**TAC Trees** — 20 constellations. Each node an agent's orbit. When P7 agents move through the interpreter, TAC trees are how you see the constellation form. `pinokio-p7.tac.yaml`: 7 phases, 20 nodes, from "agent says speak" to "audio fills the room."

**Security as Bass Line** — Phase C: 8 submodules audited, BoTZ JWT fail-open found, Neo4j injection, NATS auth gaps. 6 fixed. Bass you don't hear till it drops out.

**62 → 12 branches** — Today. Swept the stage before the show.

### 3b. Next Tracks

| Track | The Music |
|-------|-----------|
| **Commit TAC trees** | Constellation map for P7 agent routing |
| **P7 requirements** | Tuning the instrument before the set |
| **Wire P7 → CHIT** | Every "speak hello" gets coordinates in the constellation |
| **Agent signatures** | Each bandmate gets glyph + color + resonance (5090/z890/4090) |
| **Model tuning** | Faster conductor — orchestra responds quicker |

### 3c. The Snapshot

> "Dancers in the dark are lucky we can see air giving shapes to space"

- `musicMapping.ts` functions are the **instruments**
- TAC trees are the **sheet music**
- CHIT geometry bus is the **recording**
- Security hardening is the **bass line**
- When a user says "speak hello world" and it routes P7 → Pinokio → TTS → Cast speaker → the room fills — that's the **concert**

The audience says "that's my car." Because it moved like something POWERFUL.

---

## Step 4: Claude Fleet — Node Specialization (2026-03-21)

> Canonical assignments per [DnB Orchestra](./AGNOTE4482DnB.PHI.Orchestra.md) Node Specialization Matrix.

### z890-claude (⚙ #1E40AF) — Infrastructure Coordinator
| # | Task | Status |
|---|------|--------|
| 1 | ~~Triage Gemini PRs #1003-1006~~ | DONE (merged in prior sessions) |
| 2 | ~~Cherry-pick contaminated branches~~ | DONE |
| 3 | ~~P7 upgrade verified on Z890~~ | DONE (2026-03-22 — agents.js confirmed, :42000 running) |
| 4 | ~~P7 requirements validated~~ | DONE (pterm 0.0.24, ffmpeg 7.0.2, py — all present) |
| 5 | Agent Zero model tuning | Pending |
| 6 | ComfyUI first render test | Pending |
| 7 | NATS leaf node expansion to 5090 | Pending |

### 5090-claude (♫ #9333EA) — GPU Inference Specialist
| # | Task | Status |
|---|------|--------|
| 1 | Container rebuilds (4 services post-sync) | **NEXT** |
| 2 | BoTZ Dependabot PRs #89, #91 | **DONE** (both merged 2026-03-18/22) |
| 3 | TTS mesh access (GRADIO_SERVER_NAME fix) | **DONE** (start.js pushed to Pinokio fork) |
| 4 | Flute-Gateway → TTS Studio wiring | **PARTIAL** (port 7860 + 13 engines committed, container restart pending) |
| 5 | TTS session commit (port, engines, tests, personas) | **DONE** (`5c3064ebb`) |

### 4090-claude (◉ #0D9488) — Noise Reducer
| # | Task | Status |
|---|------|--------|
| 1 | ~~Upgrade Pinokio 7 on laptop~~ | DONE |
| 2 | Test P7 Agent Interpreter → 5090 TTS via Tailscale | Pending |
| 3 | Test mobile agent (Discord/Openclaw) → TTS flow | Pending |
| 4 | **Claim W1: Agent Theming + Terminal** (foundation lane) | **Recommended** |

---

## Verification

```bash
# TAC commit landed
git log --oneline -3                       # expect: TAC tree commit

# P7 requirements fixed
# Manual: Pinokio Settings → Requirements → all green

# TAC tree count
ls pmoves/configs/tac_trees/ | wc -l       # expect: 20 files (including pinokio-p7)
```

---

## Step 5: P7 Strategy Pivot — Pinokio as Mesh Transport Layer (2026-03-18)

### The Discovery

Security hardening (PR #1014) revealed the real architecture: **P7's Caddy proxy (pmoves-net) is the mesh transport layer**, not raw Tailscale IPs. P7 at `100.73.74.3:42000` serves the full Pinokio UI across the Tailscale mesh, with each app getting a proxied `42XXX` port.

Instead of fighting raw port access, P7 becomes the **agent orchestration layer**.

### Why P7 > Raw IDE

1. **Isolation:** Each agent instance has its own P7 session — no git contamination (Gemini committed chrome-ext + security changes in one commit — never again)
2. **Discovery:** P7 VPN scan finds apps across mesh automatically
3. **Customization:** SKILL.md composition lets each instance specialize
4. **Resumption:** Agent Launcher tracks sessions — pick up where you left off
5. **Mobile:** Pixel 10 Pro XL (100.103.111.121) can access any P7 instance via Tailscale

### Per-Instance Architecture

| Instance | Machine | Focus | SKILL.md Stack |
|----------|---------|-------|----------------|
| **4090-claude** | Laptop | Cast, mobile, field testing | TTS, Cast, Cipher Memory |
| **5090-claude** | 5090 Win | GPU voice, Hi-RAG | TTS (all 10 engines), Hi-RAG, Flute, Pipecat |
| **z890-claude** | Z890 | Infrastructure, Docker | PMOVES Services, Model Registry, ComfyUI |
| **gemini** | P7 instance | Broad integration, Chrome | Chrome Extension, BoTZ, Agent Cards |

### Cross-Machine Flow Example

```
4090 P7 → "speak hello"
  → Agent Interpreter discovers TTS SKILL.md on 5090 P7
  → Routes via Tailscale to 100.73.74.3:42XXX (Caddy proxy)
  → 5090 P7 → TTS Studio → audio
  → Cast to Google Home (if on same LAN)
```

### env.shared _BIND Workaround

The `_BIND` variables are in the working tree but the damage-control hook blocks git ops on env.shared. This is documented in `PORT_BINDING_MODEL.md`. The docker-compose.yml inline defaults (`${*_BIND:-127.0.0.1}`) work without env.shared. Agents running `make brand-defaults` populate env.shared programmatically.

### Agent Signature Alters (schema 1.1.0)

Restructured z890-claude and 5090-claude dual entries as `alters` array (schema 1.1.0). Both glyphs preserved as intentional persona variants — ▣/⚙ for z890, ◈/♫ for 5090. Primary identity unchanged; alters available for future persona-switching.

### SKILL.md Files Created

| File | Discovery Target |
|------|-----------------|
| `pbnj/pinokio/api/pmoves-services/SKILL.md` | Docker Compose profile controls |
| `pmoves/docs/ARTSTUFF/Ultimate-TTS-Studio.git/SKILL.md` | Multi-engine TTS (10 engines) |

### 4090-claude Test Results

- P7 installed on 4090 laptop — Agents tab visible, pmoves-net named
- Tailscale mesh: all 3 machines connected
- TTS on 5090: binds `localhost:7861` — needs `--server-name 0.0.0.0` or Caddy proxy route for mesh access
- Flute-Gateway reports `ultimate_tts: false` — TTS service not yet reachable from Flute

---

## Step 6: 5090-claude TTS Session Summary (2026-03-22)

### Completed (Committed `5c3064ebb`)

| # | Change | Files |
|---|--------|-------|
| 1 | Port 7861→7860 unification (12 files) | docker-compose, flute-gateway, cast-tts, env refs |
| 2 | 6 new engines in Flute provider (7→13) | `ultimate_tts.py` |
| 3 | Test harness rewrite (gradio_client) | `test_all_tts_engines.py` |
| 4 | Voice personas catalog | `.claude/context/voice-personas.md` |
| 5 | Gradio 408 fix (GRADIO_SERVER_NAME=127.0.0.1) | Pinokio fork `start.js` (pushed to main) |

### Remaining (This Session) — RESOLVED 2026-03-22

| # | Task | Status |
|---|------|--------|
| 1 | Container rebuilds (tensorzero, YT, BoTZ, cipher-memory) | **DELEGATED** → z890-claude (has full env vars) |
| 2 | ~~Flute container restart + healthcheck~~ | **DONE** — fixed Gradio 4.x API migration + 121-param alignment |
| 3 | ~~13-engine sweep~~ | **DONE** — 10/14 via Flute-Gateway, 11/14 direct synthesis |

### Deferred (Next Session)

| # | Task | Why |
|---|------|-----|
| 1 | GPU model serving validation (Ollama 17/17) | Orchestra task |
| 2 | Pipecat WebSocket design (8056) | Flute wiring done — ready to implement |
| 3 | Media pipeline e2e (YT → Whisper → Hi-RAG) | Independent track |
| 4 | W1 CLI bridge + W3 Discord | Roadmap items |
| 5 | Fish S2 Pro via Flute (timeout) | Raise `ULTIMATE_TTS_TIMEOUT_SEC` to 300 |
| 6 | Flute-Gateway Docker image rebuild | z890 has Supabase env vars needed for compose build |

---

## Step 7: Voice Stack Activation Results (2026-03-22)

### Bug Fixed: UltimateTTSProvider Gradio 4.x Migration

**PR #1069** — `fix(flute-gateway): migrate UltimateTTSProvider to Gradio 4.x event API`
**Commit:** `24305c4f2`
**File:** `pmoves/services/flute-gateway/providers/ultimate_tts.py`

Two critical issues found and fixed:
1. Dead Gradio `/api/` predict endpoint (404) → migrated to `/gradio_api/call/` event-based SSE
2. 92-param array → 121-param array (TTS Studio API grew since provider was written)

Also fixed: engine names (`Fish Speech S1`, `Qwen Voice Design`, `Chatterbox Multilingual`), load params (`F5-TTS Base`, Qwen `model_type`/`model_size`).

### Flute-Gateway Engine Sweep (10/14 pass)

| Engine | Size | Time | Status |
|--------|------|------|--------|
| KittenTTS | 434KB | 1.2s | **PASS** |
| Kokoro | 425KB | 7.3s | **PASS** |
| ChatterboxTTS | 250KB | 12.2s | **PASS** |
| F5-TTS | 249KB | 10.7s | **PASS** |
| Fish Speech S1 | 344KB | 27.5s | **PASS** |
| VoxCPM | 522KB | 25.8s | **PASS** |
| Qwen Voice Design | 206KB | 17.8s | **PASS** |
| IndexTTS | 225KB | 13.6s | **PASS** |
| Chatterbox Turbo | 198KB | 40.8s | **PASS** |
| Chatterbox MTL | 182KB | 117.9s | **PASS** |
| Fish S2 Pro | — | >120s | **TIMEOUT** (4B model, needs higher timeout) |
| IndexTTS2 | — | — | **SKIP** (requires emotion ref_audio) |
| Higgs Audio | — | — | **SKIP** (load timeout) |
| VibeVoice | — | — | **SKIP** (separate endpoint, not unified API) |

### STT Round-Trip Verification (6/6 perfect)

| Source | Engine | Result |
|--------|--------|--------|
| Direct WAV | Kokoro | Exact match |
| Direct WAV | KittenTTS | Exact match |
| Direct WAV | Chatterbox | Exact match (2 segments) |
| Flute REST | F5-TTS | "fourteen" → "14" (semantic match) |
| Flute REST | Qwen | "fourteen" → "14" (semantic match) |
| Flute REST | VoxCPM | "fourteen" → "14" (semantic match) |

### Unblocks for Other Nodes

| Unblock | Beneficiary | How |
|---------|------------|-----|
| Flute→TTS chain works | **All nodes** | `POST http://100.73.74.3:8055/v1/voice/synthesize/audio` |
| Pterm lifecycle validated | **4090-claude** | Can start/stop TTS Studio remotely via Tailscale mesh |
| `127.0.0.1` not `localhost` | **z890-claude** | Docker containers must use `host.docker.internal` for host services |

### Delegations

**z890-claude:**
- Container rebuilds (tensorzero, YT, BoTZ, cipher-memory) — z890 has full env chain
- Flute-Gateway Docker image rebuild (compose build needs Supabase env vars)
- Agent Zero model tuning (pending)
- ComfyUI first render test (pending)

**4090-claude:**
- Test P7 Agent Interpreter → 5090 TTS via Tailscale — **UNBLOCKED**
- Test mobile agent (Discord/Openclaw) → TTS flow — **UNBLOCKED**
- Claim W1: Agent Theming + Terminal (recommended per roadmap)

---

## Critical Files

| File | Purpose |
|------|---------|
| `pmoves/configs/tac_trees/pinokio-p7.tac.yaml` | P7 integration TAC tree |
| `pmoves/configs/tac_trees/voice-agents.tac.yaml` | Voice pipeline TAC (Phase 15: P7 routing) |
| `pmoves/config/agent_registry.yaml` | Agent identity (z890/5090/4090-claude) |
| `pmoves/config/agent_signatures.yaml` | Visual identity — deduplicated |
| `pmoves/docs/security/PORT_BINDING_MODEL.md` | Port binding model + env.shared workaround |
| `pbnj/pinokio/api/pmoves-services/SKILL.md` | PMOVES Services skill for P7 |
| `pmoves/docs/ARTSTUFF/Ultimate-TTS-Studio.git/SKILL.md` | TTS skill for P7 |
| `D:\pinokio\` | P7 install (upgraded, requirements pending) |
