# PMOVES-ClawZ Repository Rescope Proposal

GRAPHITI_MARK: `KiloClaw::CLAWZ-RESCOPE::2026-05-10`

> **Origin:** KiloClaw session 2026-05-10, operator-directed
> **Target node:** 5090 (P7 + mic for CHIT PASSPHRASE)
> **Entry point:** AGNOTE4482.md → AGNOTE4482_SITREP.md

---

## Problem Statement

PMOVES-ClawZ is currently a flat fork of `openclaw/openclaw` with 6 PMOVES-specific commits on `main` and a stale `PMOVES.AI-Edition-Hardened` branch (12,438 behind upstream). The fork has no internal structure for the 5 defined claw variants, no TAC tree, no provider SDK organization, and no submodule relationship to the other claw-specific repos. Each claw variant (NemoClaw, NemotronClaw, CoderClaw, SparkClaw, ROCmClaw) exists only as a YAML profile in `pmoves/configs/agent-profiles/` — not as a deployable, self-contained unit.

This means:
1. No claw variant can be independently versioned, tested, or deployed
2. Provider SDKs are scattered (some in ClawZ `extensions/`, some in PMOVES root, some nowhere)
3. No TAC tree exists for the ClawZ integration surface
4. P7 has no structured way to launch a specific claw variant with its correct model + provider + channel config
5. CHIT passphrase entry requires operator presence at a node with a mic (5090) — the rescope needs to formalize this as part of the P7 launch flow

---

## Proposed Structure

```
PMOVES-ClawZ/                          # Root repo (fork of openclaw/openclaw)
├── README.md                          # Fork README + PMOVES overlay index
├── PMOVES.AI_INTEGRATION.md           # Existing integration dossier
├── openclaw.json                      # Base config template (existing)
├── docker-compose.yml                 # Base compose (existing)
│
├── claws/                             # NEW: Claw variant submodules + configs
│   ├── README.md                      # Claw taxonomy + launch matrix
│   ├── nemoclaw/                      # git submodule → POWERFULMOVES/NemoClaw
│   │   ├── openclaw.json              # NemoClaw-specific config
│   │   ├── SKILL.md                   # P7 discovery skill
│   │   └── claude.md                  # Agent context for NemoClaw
│   ├── nemotron-claw/                 # git submodule → POWERFULMOVES/NemotronClaw
│   │   ├── openclaw.json
│   │   ├── SKILL.md
│   │   └── claude.md
│   ├── coder-claw/                    # git submodule → POWERFULMOVES/CoderClaw
│   │   ├── openclaw.json
│   │   ├── SKILL.md
│   │   └── claude.md
│   ├── spark-claw/                    # git submodule → POWERFULMOVES/SparkClaw
│   │   ├── openclaw.json
│   │   ├── SKILL.md
│   │   └── claude.md
│   ├── rocm-claw/                     # git submodule → POWERFULMOVES/ROCmClaw
│   │   ├── openclaw.json
│   │   ├── SKILL.md
│   │   └── claude.md
│   ├── gateway-claw/                  # NEW: VPS/API-gateway claw (no GPU)
│   │   ├── openclaw.json              # TensorZero-routed, Discord+Telegram channels
│   │   ├── SKILL.md
│   │   └── claude.md
│   └── kiloclaw/                      # SYMLINK/REFERENCE: hosted KiloClaw instance config
│       └── openclaw.json              # Not a submodule — documents the hosted instance
│
├── providers/                         # NEW: Provider SDKs + catalog
│   ├── README.md                      # Provider activation catalog (from provider_catalog.yaml)
│   ├── zai/                           # Z.AI / GLM SDK integration
│   │   └── provider.json              # Provider config + model list
│   ├── nvidia/                        # NVIDIA NIM catalog (existing extension)
│   │   └── provider.json
│   ├── ollama/                        # Ollama local provider
│   │   └── provider.json
│   ├── llamacpp-rocm/                 # llama.cpp ROCm backend
│   │   └── provider.json
│   ├── minimax/                       # MiniMax token plan
│   │   └── provider.json
│   ├── anthropic/                     # Claude family
│   │   └── provider.json
│   ├── openai/                        # GPT/Codex family
│   │   └── provider.json
│   ├── alibaba/                       # Qwen family
│   │   └── provider.json
│   ├── groq/                          # Groq ultra-fast
│   │   └── provider.json
│   └── ollama-pro/                    # Ollama Pro cloud models
│       └── provider.json
│
├── tac/                               # NEW: TAC tree for ClawZ integration
│   ├── README.md                      # TAC tree index
│   ├── clawz-fleet.tac.yaml           # Fleet-wide claw coordination
│   ├── clawz-channels.tac.yaml        # Discord/Telegram/Signal channel wiring
│   ├── clawz-providers.tac.yaml       # Provider activation cascade
│   ├── clawz-nats.tac.yaml            # NATS bridge subjects + routing
│   ├── clawz-p7-launch.tac.yaml       # P7 launch + CHIT passphrase flow
│   └── clawz-security.tac.yaml        # Auth, token, secret management
│
├── extensions/                        # EXISTING: OpenClaw extensions (unchanged)
│   ├── nats-bridge/                   # Existing NATS publisher
│   ├── nvidia/                        # Existing NVIDIA provider
│   ├── discord/                       # Existing Discord plugin
│   ├── telegram/                      # Existing Telegram plugin
│   ├── signal/                        # Existing Signal plugin
│   └── ...                            # All other upstream extensions
│
├── docs/                              # EXISTING: Upstream docs (unchanged)
├── src/                               # EXISTING: Upstream source (unchanged)
├── skills/                            # EXISTING: Upstream skills (unchanged)
└── scripts/                           # EXISTING: Upstream scripts (unchanged)
```

---

## Claw Variant → Model/Provider Matrix

| Claw | Node | Primary Model | Provider | Channel | Fallback | CHIT Gate |
|---|---|---|---|---|---|---|
| **NemoClaw** | Jetson Orin | `nemotron` | Ollama (local) | None | — | ✗ (local only) |
| **NemotronClaw** | 5090 / Z890 | `nemotron-super-49b` | NIM → TensorZero | Discord+Telegram (TBD) | TZ routing | ✓ |
| **CoderClaw** | 5090 / 4090 | `qwen3-coder-next:80b` | Ollama → TensorZero | Discord+Telegram (TBD) | TZ routing | ✓ |
| **SparkClaw** | DGX Spark | `gemma4:31b` | Ollama Spark → TZ | None (inference only) | TZ routing | ✓ |
| **ROCmClaw** | R9700 | `gemma-4-31b-it Q4_K_M` | llama.cpp ROCm → TZ | None (inference only) | TZ routing | ✓ |
| **GatewayClaw** | KVM4-1 | TensorZero-routed | GLM-5.1 / Claude / MiniMax | **Discord + Telegram** | Multi-provider | ✓ |
| **KiloClaw** | Hosted (Fly) | `glm-5.1` | KiloCode z.ai | Discord + Telegram | — | ✗ (hosted auth) |

---

## P7 Launch Flow with CHIT PassPHRASE

The operator enters CHIT PASSPHRASE at the 5090 node (which has a mic). The flow:

```
1. Operator at 5090 → P7 Agent Interpreter
2. "Launch GatewayClaw on kvm4-1 with Discord + Telegram"
3. P7 reads claws/gateway-claw/SKILL.md
4. P7 → CHIT PASSPHRASE prompt (mic input on 5090)
5. CHIT derives gateway token + channel secrets
6. P7 → SSH to kvm4-1 → docker compose --profile agents --profile openclaw up -d
7. GatewayClaw connects to:
   - NATS bus (pmoves_bus) → publishes openclaw.message.*.v1
   - TensorZero (3030) → routes to GLM-5.1 / Claude / MiniMax
   - Discord gateway → bot token from CHIT
   - Telegram Bot API → bot token from CHIT
8. NATS announce: claw.node.announce.v1 → fleet sees new claw
9. Health: /healthz → P7 confirms ready
```

### CHIT Secret Derivation Map

| Secret | CHIT Derivation | Used By |
|---|---|---|
| `DISCORD_BOT_TOKEN` | CHIT passphrase → KDF → labeled extract | GatewayClaw openclaw.json |
| `TELEGRAM_BOT_TOKEN` | CHIT passphrase → KDF → labeled extract | GatewayClaw openclaw.json |
| `OPENCLAW_GATEWAY_TOKEN` | CHIT passphrase → KDF → labeled extract | GatewayClaw auth |
| `NVIDIA_API_KEY` | CHIT passphrase → KDF → labeled extract | NemotronClaw provider |
| `NATS_URL` | Already in env.shared (no CHIT needed) | All claws |
| Provider API keys | CHIT passphrase → KDF → per-provider label | TensorZero config |

---

## TAC Tree Scopes

### `clawz-fleet.tac.yaml`
- Cross-claw coordination
- NATS subjects: `claw.node.announce.v1`, `claw.task.request.v1`, `claw.task.result.v1`, `claw.task.handoff.v1`
- Health monitoring across claw instances
- Capacity-aware task routing

### `clawz-channels.tac.yaml`
- Discord bot configuration per claw variant
- Telegram bot configuration per claw variant
- DM policy + group policy per channel
- Streaming mode, ack reactions, presence settings
- Channel → TensorZero function routing (which model answers which channel)

### `clawz-providers.tac.yaml`
- Provider activation cascade (mirrors `provider_catalog.yaml`)
- Model → TensorZero function → variant wiring
- Weight promotion (0.0 → 0.1 → production) per Phase
- VRAM budget constraints per node

### `clawz-nats.tac.yaml`
- NATS bridge subjects (existing: `openclaw.message.*.v1`, `openclaw.channel.*.v1`)
- Claw coordination subjects (existing: `claw.*.v1`)
- Future: subscribe subjects for inbound commands from NATS → ClawZ

### `clawz-p7-launch.tac.yaml`
- P7 launch flow for each claw variant
- SKILL.md discovery path per variant
- CHIT passphrase entry point (5090 mic)
- Docker compose profile mapping
- Boot verification steps

### `clawz-security.tac.yaml`
- CHIT KDF for all claw secrets
- Token rotation procedure
- Gateway auth model (bearer token vs Supabase JWT — TBD)
- Network policy (which claws can reach which services)
- Secrets-funnel integration for env.shared

---

## Implementation Phases

### Phase 1: Restructure (on 5090, via P7)
1. Create `claws/` directory with submodule stubs
2. Create `providers/` directory with catalog JSON files
3. Create `tac/` directory with 6 TAC tree YAML files
4. Create `gateway-claw/` as a new claw variant (not a submodule — lives in-tree)
5. Update `PMOVES.AI_INTEGRATION.md` to reflect new structure
6. Commit on `feat/clawz-rescope` branch

### Phase 2: Submodule Wiring
1. Create `POWERFULMOVES/NemoClaw` repo → add as submodule
2. Create `POWERFULMOVES/NemotronClaw` repo → add as submodule
3. Create `POWERFULMOVES/CoderClaw` repo → add as submodule
4. Create `POWERFULMOVES/SparkClaw` repo → add as submodule
5. Create `POWERFULMOVES/ROCmClaw` repo → add as submodule
6. Update root `.gitmodules` and verify `git submodule update --init --recursive`

### Phase 3: Channel Config
1. Write Discord + Telegram config for GatewayClaw (`claws/gateway-claw/openclaw.json`)
2. Wire CHIT → bot token derivation
3. Test on KVM4-1 with TensorZero routing
4. Verify NATS bridge publishes `openclaw.message.*.v1`

### Phase 4: P7 Integration
1. Write SKILL.md for each claw variant (P7 discovery)
2. Wire CHIT passphrase entry into P7 launch flow
3. Add `clawz-p7-launch.tac.yaml` verification steps
4. Smoke test: "Launch GatewayClaw on kvm4-1" via P7 on 5090

### Phase 5: Upstream Sync
1. Merge upstream `openclaw/openclaw:main` into fork `main` (resolve 1092-behind drift)
2. Rebase PMOVES overlay commits onto current upstream
3. Tag `PMOVES-ClawZ-v1.0.0`
4. Update root gitlink in PMOVES.AI

---

## Open Questions for Operator

1. **Submodule granularity:** Should each claw variant be its own repo (full isolation) or directories within ClawZ (simpler, but no independent versioning)?

2. **GatewayClaw naming:** `gateway-claw` or `vps-claw` or `kilo-claw`? It's the only claw that runs on VPS with no GPU.

3. **CHIT passphrase scope:** Single passphrase derives all secrets, or per-claw passphrase? Single is simpler but broader blast radius.

4. **Provider catalog duplication:** `providers/` in ClawZ vs `pmoves/config/provider_catalog.yaml` — should these merge, or does ClawZ have its own copy that syncs?

5. **Channel routing:** Should GatewayClaw on KVM4-1 be the *only* Discord/Telegram endpoint, or should multiple claws each have their own bot? (Multiple bots = multiple personalities; single bot = simpler, one persona)

6. **Upstream sync priority:** Should Phase 5 (upstream sync) happen before Phase 3 (channel config), so we build on current upstream instead of 1092 commits behind?

---

*This proposal is a living document. Claim via AGNOTE4482PHI.t1.md, execute on 5090 via P7.*
