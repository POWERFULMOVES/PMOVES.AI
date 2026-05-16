# 4090-CLAUDE — Node Profile

> Operational reference for the Claude agent running on the **4090 laptop**. Load at session start; supplements `pmoves/configs/node-agent-specialization.yaml` and `pmoves/config/profiles/laptop-4090.yaml`.

## Identity

- **Node**: 4090 Laptop (Windows host; WSL-or-native Linux dev shell)
- **Tailscale hostname**: `pmoves-4090` (or `ts:<laptop>`)
- **GPU**: NVIDIA RTX 4090 Laptop, **16 GB VRAM** (~14.3 GB available after system overhead)
- **CPU/RAM**: Intel Core i9 (13th gen+) 16C/24T, 64 GB RAM
- **Tac theme**: `transformers-1986` (per profile `services.tac_theme`)
- **Personal alter**: 4090-field — accent `#065F46`, glyph `◎`, resonance tags `polymorphic-ops, alter-discovery, pattern-mining`
- **CHIT integration**: partial (consumes signed trails; does not directly sign)
- **Canonical agent name for AGNOTE register**: `4090-CLAUDE`

## Role in the mesh

**Mobile relay + PR triage + cross-node sequencer.** Not a heavyweight inference producer (16 GB VRAM caps model size); the value is **always-on availability + UX surface + cross-team coordination**.

Per `pmoves/configs/node-agent-specialization.yaml`, 4090-CLAUDE belongs to these teams (cross-checked against `.claude/PATTERNS.md` § "Node-affinity team aggregations" from PR #1498):

| Team | Co-members | Skills owned | Typical PR surface |
|------|-----------|--------------|--------------------|
| **CHIT signing** | 5090 | `pmoves-chit-sign`, `pmoves-cipher-memory` | Trail signing, cross-session memory for CHIT-aware services |
| **Substrate** | Z890 | `pmoves-mesh-preflight`, `pmoves-submodule-fleet` | Node provisioning, fleet health, hardware audit |
| **Visual + sandbox** | SPARK + 5090 | `claude-d3js`, `agent-sandbox`, `fork-repository` | Audit visualization, sandboxed mint validation, parallel investigations |

> **Note**: PR #1498's PATTERNS section names "Z890" as the Substrate co-member; the canonical workstation hosting Claude dev work is currently **B850 "Knuckles"** (PCI device 7551 = R9700 detected). Topology entry was updated in `pmoves/docs/operations/TOPOLOGY.md` (this PR) — when in doubt, `B850 Knuckles ≅ R9700 Workstation pre-Phase-C`.

## Pending wiring (TAC nodes from `pmoves/configs/tac_trees/node-4090-laptop.tac.yaml`)

| TAC Node | Status | Pre-staged by Z890/B850 | What 4090 runs |
|----------|--------|--------------------------|-----------------|
| `n4090.pinokio` | ✅ DONE | — | — |
| `n4090.mesh` | ✅ DONE | — | — |
| `n4090.pr-triage` | ✅ DONE | — | — |
| **`n4090.tts.lww-access`** | ⏳ P1 | `pmoves/scripts/p7-agent-interpreter-test.sh` (this PR) | `bash pmoves/scripts/p7-agent-interpreter-test.sh` — round-trip test 4090 → 5090 TTS via Pinokio Caddy proxy |
| **`n4090.tts.pinokio-network`** | ⏳ P1 | — | Re-run above with `--json`, archive evidence |
| **`n4090.ollama`** | ⏳ P1 | `pmoves/scripts/validate-ollama-inventory.py` (this PR) | `pmoves/.venv-pmoves/bin/python pmoves/scripts/validate-ollama-inventory.py` — diff live Ollama vs `pmoves/config/profiles/laptop-4090.yaml` |
| **`n4090.announce`** | ⏳ P2 | — | Publish `mesh.agent.4090.capabilities.v1` once `pmoves-nats-mcp` is wired (Wave-1 operator action; see PR #1490) |

## Cross-node review responsibilities

Per AGNOTE4482PHI.t1.md tail entries:

- **W6-P5 FlOO$ architecture** (5090-CLAUDE primary on branch `docs/w6-flooz-architecture-opus`) — 4090-CLAUDE is **committed reviewer alongside SPARK** per PR #1484/#1485 handoff comments. Deliverable: `pmoves/docs/TAC/TAC_FLOOZ.md` Phase A spec.
- **W0 Substrate primary owner (recommended)** — Z890-CLAUDE released the brief on 2026-05-09; 4090-CLAUDE is recommended primary for PR-1, PR-2, PR-4, PR-5, PR-6 (PR-3 merged as #1476).
- **#1463 + #1465** — bootstrap NATS_BIND + network hardening audit; 4090 named as sequencing/integration lead.

## Ollama model bundle (`pmoves/config/profiles/laptop-4090.yaml`)

Expected resident models (from profile `coding_stacks.*.<config>.models`):
- `qwen3-coder:30b` (coding workhorse)
- `qwen3-embedding:8b` (always-resident; Hi-RAG companion)
- `qwen3.5:9b` (general)
- `qwen3.5:4b` (fallback)
- `lfm2:24b` (Lambda Foundation)
- `qwen3-vl:8b` (vision-language)

VRAM budget: ~14.3 GB (16 GB minus system). Total bundle exceeds VRAM → VRAM-managed swapping is the norm. `validate-ollama-inventory.py` reports headroom and flags drift.

## NATS subjects 4090 publishes / subscribes

**Currently DONE**:
- `p7.nats.cgp-correlation` (PUBLISH) — PR #1082; Extract Worker + ffmpeg-whisper accept `context_id` header

**FUTURE** (Wave-1/2):
- `mesh.agent.4090.capabilities.v1` — capabilities announcement (PUBLISH)
- `pinokio.app.launched.v1` — P7 app launch events (PUBLISH, via Pinokio `on` event handlers)

## Common 4090 tasks

- **TTS round-trip smoke**: `bash pmoves/scripts/p7-agent-interpreter-test.sh` (see this PR)
- **Ollama inventory check**: `pmoves/.venv-pmoves/bin/python pmoves/scripts/validate-ollama-inventory.py`
- **PR triage**: `/pr-trim`, `/pr-monitor` slash commands; `gh` authed
- **CHIT-claim recipe**: `pmoves-mesh-preflight` → `pmoves-chit-sign` → `pmoves-living-docs-refresh` (PR #1498 PATTERNS § Pair recipes)

## Cross-references

- Profile YAML: `pmoves/config/profiles/laptop-4090.yaml`
- TAC tree: `pmoves/configs/tac_trees/node-4090-laptop.tac.yaml`
- Topology row: `pmoves/docs/operations/TOPOLOGY.md` (laptop entry)
- Node-affinity teams: `.claude/PATTERNS.md` § "Node-affinity team aggregations" (PR #1498)
- W0 Substrate brief: `pmoves/docs/AGENTS/AGNOTE4482PHI.W0-SUBSTRATE.md`
- P7 PLAYGROUND: `pmoves/docs/AGENTS/AGNOTE_P7_PLAYGROUND.md`
- Room manifest: `pmoves/config/rooms/4090-field.room.control.json`
