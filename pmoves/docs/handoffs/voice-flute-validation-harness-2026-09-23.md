# Voice Lane 1 — flute-gateway validation harness — task card 2026-09-23

**Date:** 2026-09-23
**From:** elder-melchor Hermes dispatch (voice-stack heal session, 2026-09-23)
**To:** **5090-claude** (primary implementer) · z890-claude (secondary — registry affinity is `[5090, z890]`)
**Coordination:** Village Rule — CLAIM this lane in `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` before starting item work; release with an ACK line when done.
**Related:** PR #2977 (flute-voice MCP surface), PR #2024 (kokoro CPU floor),
`pmoves/docs/services/VOICE_FABRIC_PLAN.md`, `pmoves/mk/voice.mk`, `pmoves/Makefile` FLUTE-GATEWAY section.
**Status:** OPEN (unclaimed)

---

## Current receipted state (measured, not asserted)

The elder-node voice stack was healed **2026-09-23**: a down Docker Desktop engine produced
WinError 10061 on the kokoro CPU floor (`:8004`) and flute-gateway (`:8055`); both returned
`healthz` 200 after engine relaunch. That heal is the receipt this lane builds on. The gap:
proving it required hand-rolled curls. **There is no single harness.**

| Surface | State | Receipt / where it lives |
|---|---|---|
| flute-gateway | up, `:8055` healthz 200 (2026-09-23 heal) | `make -C pmoves flute-gateway-smoke` — **healthz ONLY** (`Makefile:4757`) |
| kokoro floor | up, `:8004` healthz 200; 0-VRAM default for Hermes read-aloud | `make -C pmoves kokoro-smoke` (`mk/voice.mk:39`; image `pmoves-kokoro-tts:latest`, 127.0.0.1:8004, 2CPU/2G, model digest-pinned) |
| registry entry | `flute_gateway` port 8055, health `/healthz`, layers `[L0,L2,L2.5,L4]`, team media | `pmoves/config/agent_registry.yaml:909` |
| NATS contract | publishes `tokenism.geometry.event.v1`, `tokenism.prosodic.bpm.v1`; subscribes `geometry.packet.decoded.v1` | same registry block — **declared, not observed** (Step 4 settles it) |
| profile metadata | registry says `compose_profile: agents`; the known road starts flute with `--profile orchestration` | `agent_registry.yaml:935` vs `Makefile:4742` — **drift; verify before relying on either** (Step 6) |
| MCP surface | `:8055/sse` + POST `/mcp` (streamable, 2026-09-12), 6 `tts_*` tools | `pmoves/tests/test_flute_mcp_streamable.py` (7 tests) |
| partial harnesses today | `flute-gateway-smoke` (healthz), `voice-host-affinity-smoke` (routing `node` assert), `kokoro-smoke`, `voice-cast-smoke` (CHIT sign) | `Makefile:4757`, `mk/voice.mk:142`, `mk/voice.mk:39`, `mk/voice.mk:124` |
| auth dialect | `X-API-Key` header (NOT Bearer); unset `FLUTE_API_KEY` = dev mode, skipped | `pmoves-voice-fabric` skill; key readable via `docker exec pmoves-flute-gateway-1 printenv FLUTE_API_KEY` (`mk/voice.mk:112`) |

**The gap this lane closes:** after an engine heal (or on any fresh node), "flute is up" is
currently three separate hand-run probes and a hope. Nothing asserts the *chain*: bus →
gateway → provider dispatch → kokoro floor → declared NATS subjects actually firing. The
known failure mode (voicebox 4GB-VRAM wedge on GTX 1650-class GPUs; flute 502 when its GPU
backend is empty) is documented in the `pmoves-voice-fabric` skill but machine-checked nowhere.

## Target state

One command — `make -C pmoves flute-validation` — runnable by any node agent or operator
post-heal, which:

1. proves the chain: NATS bus reachable → flute healthz → config probe → per-engine synthesis;
2. covers the kokoro floor BOTH ways (direct `:8004` AND via flute `ultimate_tts` +
   `engine=kokoro` — the only in-dispatch route, KokoroProvider is not wired top-level);
3. observes the registry-declared NATS subjects; **declared-not-wired is a FAIL that names the
   subject**, never a silent pass;
4. includes a negative control: kokoro down → flute must fail LOUD (silent fallback is the
   bug class this fleet keeps finding);
5. writes a machine-readable receipt (`out/flute-validation-report.json`) and a decisive exit
   code for CI / agent use.

## Steps (bite-sized, exact commands)

### Step 0 — claim + baseline receipts (~30 min)

Claim the lane (see Coordination), then on a node with the stack up (elder has the freshest
post-heal state; 5090 after its own bring-up):

```bash
make -C pmoves svc-status SVC=flute-gateway
curl -sS http://localhost:8055/healthz
curl -sS http://localhost:8055/v1/voice/config
curl -sS http://localhost:8004/healthz
```

Record all four outputs verbatim — they are the "before" the harness must reproduce.

### Step 1 — scaffold the harness

Create `pmoves/scripts/voice/flute_validation.sh`, modeled on the conventions of
`pmoves/scripts/voice/host_affinity_smoke.sh` (self-verifying exit codes; curl + python3
only, **no jq dependency**; env overrides; `log`/`fail` helpers; `set -euo pipefail`).

Checks, in order:

1. `GET :8055/healthz` → 200
2. `GET :8004/healthz` → 200 (kokoro floor precondition)
3. `GET :8055/v1/voice/config` → providers list non-empty
4. `POST :8055/v1/voice/synthesize` (omnivoice default) → non-empty audio bytes
5. `POST :8055/v1/voice/synthesize` with `{"provider":"ultimate_tts","engine":"kokoro"}` → non-empty audio bytes

Auth: pull the key with
`docker exec pmoves-flute-gateway-1 printenv FLUTE_API_KEY 2>/dev/null`
and send as `X-API-Key`; when empty, omit the header (dev mode) and log that auth was skipped.
Use `127.0.0.1`, never `localhost`, for any host-side NATS/curl URL — the IPv6-first trap is
documented at `mk/voice.mk:98-100`.

### Step 2 — NATS observation (declared vs wired)

While firing one synthesis, observe the declared subjects:

```bash
nats sub -s nats://nats:pmoves@127.0.0.1:4222 --count 1 "tokenism.>"
```

Assert ≥1 event on `tokenism.prosodic.bpm.v1` or `tokenism.geometry.event.v1`. If a declared
subject never fires, the harness FAILS and names the subject — do not patch the harness to
pass; either wire the publish or file the drift against the registry row.

### Step 3 — negative control (the gate must be able to say no)

```bash
make -C pmoves kokoro-down
# assert: flute synth with engine=kokoro fails LOUD (5xx), NOT a silent success
make -C pmoves kokoro-up   # restore; re-run Step 1 checks → PASS
```

A gate that has never been made to fail on purpose is untrusted (fleet control-specimen
rule, `CONTROL_4090-CLAUDE_PRE-GROUNDING.md` §2.2). Paste the failing run in the PR body.

### Step 4 — wire the known road

Add `flute-validation` to `pmoves/mk/voice.mk` (+ `.PHONY`), composing the script above.
Then per the node-edition convention:

```bash
docker compose --env-file <chain> -f pmoves/docker-compose.base.yml ... config --quiet  # rc 0 gate
wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/c/<repo>/pmoves && make -n flute-validation'
```

### Step 5 — registry drift check

Determine which profile actually governs flute bring-up (`compose_profile: agents` in
`agent_registry.yaml:935` vs `--profile orchestration` in `Makefile:4742`):
`docker inspect pmoves-flute-gateway-1` labels + the compose invocation that started it.
Fix the wrong surface in this PR with the evidence cited.

### Step 6 — tests + PR

- Any Python helper gets pytest coverage mirroring `tests/test_flute_mcp_streamable.py` style.
- Check `pmoves/configs/pytest_ratchet/_known_failures.yaml:241` (known-fail:
  `test_validation_script_checks_flute_gateway`) so the ratchet doesn't collide.
- PR with explicit `-R POWERFULMOVES/PMOVES.AI` on every `gh` call; conventional commit
  subjects; **merge is operator-gated**.

## Validation receipts (what "done" means)

- `make -C pmoves flute-validation` exits 0 post-heal; `out/flute-validation-report.json`
  contains: healthz codes (8055 + 8004), provider count, per-engine synth byte counts,
  NATS events observed per subject, negative-control result.
- PR body pastes: one full PASS run, one deliberate-FAIL run (Step 3), the WSL `make -n`
  dry-run, and the compose `config --quiet` rc.
- Registry drift resolved or filed with evidence.

## Node affinity

- **Primary: 5090-claude** — registry affinity `[5090, z890]`, 5090 owns the flute delta lane
  (see `docs/handoffs/5090-lane-dispatch-handoff-2026-09-11.md` lane 3).
- Secondary: z890-claude.
- Elder note: first receipts (Step 0) can run on elder now — the 2026-09-23 heal receipts
  live there — but the lane lands from a 5090/z890 worktree.

## Skills to load before starting

| Skill | Why |
|---|---|
| `pmoves-voice-fabric` | **Required.** Provider dispatch truth, kokoro-floor routing, auth dialect, VRAM discipline |
| `pmoves-registry-first` | **Required.** This lane adds launch-verify tooling; registry data drives it |
| `pmoves-node-edition-services` | mk/ compose conventions, compose-validate, WSL make dry-run |
| `pmoves-ci-gates` | If the ratchet / gitlink gate fires on the PR |
| `hermes-pmoves-pr-review` | PR discipline for this repo |

## Guardrails / out of scope

- **voicebox GPU synthesis stays OFF by default** in the harness — 4GB-VRAM wedge history
  (both Qwen 1.7B loads; meta-tensor lazy-load crash on cold boot). Voicebox is opt-in
  behind an env flag only.
- No changes to provider code — this lane measures, it does not re-route.
- CHIT-signing depth and Layer-2 engine manifests stay in their own lanes
  (`docs/services/VOICE_FABRIC_PLAN.md` sequencing 2–4).
