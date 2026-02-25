# Submodule Production Release Checklist
_Last updated: 2026-02-24_

## Goal
Deterministic release checklist for all tracked submodules before final production promotion (`PMOVES.AI-Edition-Hardened-Integrations` -> `PMOVES.AI-Edition-Hardened` -> `main`).

## Current Release Wave Status (2026-02-24)
- Completed merge sequence:
  - `#703` parity remediation
  - `#704` deterministic submodule branch gate + production checklist
  - `#700 -> #701 -> #702` Jellyfin creator production lane
  - `#699` final promotion merge to `main` (`1a21c038`)
- Remaining before next promotion wave:
  - Recover self-hosted runner queue deadlock and rerun one targeted hardening + GHCR lane for fresh evidence
  - Close credentials/runtime blockers (`AB-4`, `AB-5`, `AB-6`) in production audit dashboard
  - Re-run deterministic gate chain against next promotion head before opening new production PR stack

## Global Deterministic Gates (Run In Order)
1. `make -C pmoves submodule-layer-validate-all-strict`
2. `make -C pmoves submodule-layer-validate-strict`
3. `make -C pmoves submodule-branch-policy-check`
4. `make -C pmoves submodule-integrity-strict`
5. `make -C pmoves submodule-docs-audit-strict`
6. `make -C pmoves integration-contract-check-baseline`
7. `make -C pmoves tooling-audit-strict`
8. `make -C pmoves secrets-audit`
9. `make -C pmoves ci-runners-lockdown-strict`
10. `SUPABASE_RUNTIME=compose make -C pmoves supa-runtime-guard`
11. `make -C pmoves smoke-prod`
12. `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu` (required when any GPU lane is touched)

## Hardened Branch Requirements
- `.gitmodules` submodule branch pins must follow hardened policy.
- Deterministic checker:
  - `make -C pmoves submodule-branch-policy-check`
  - default branch: `PMOVES.AI-Edition-Hardened`
  - explicit allowed override: `PMOVES-DoX=PMOVES.AI-Edition-Hardened-DoX`
- Submodule pointers must be clean (`git submodule status --recursive` with no `-`, `+`, `U`).

## Gate Pack Legend
- `S`: static submodule gates (`submodule-layer-*`, branch policy, integrity, docs audit)
- `C`: CI/security gates (`integration-contract-check-baseline`, tooling/secrets audits, runner lockdown, `integration-gate`)
- `R1`: core runtime gate (`make -C pmoves smoke-prod`)
- `R2`: GPU runtime gate (`GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu`)
- `R3`: media runtime gate (`make -C pmoves jellyfin-stack-prod-verify && make -C pmoves yt-jellyfin-smoke && make -C pmoves jellyfin-parity-audit-strict`)
- `R4`: external app gate (`make -C pmoves smoke-wger && make -C pmoves smoke-firefly && make -C pmoves notebook-workbench-smoke`)

## Dependency Profiles
| Profile | Required dependencies |
| --- | --- |
| `P1 Agent/MCP` | NATS (credentialed), Supabase JWT (`SUPABASE_JWT_SECRET`), Agent Zero/Archon connectivity |
| `P2 Knowledge/LLM` | Qdrant, Neo4j, Meilisearch, TensorZero, Supabase |
| `P3 Media/Voice` | PMOVES.YT, Whisper, Jellyfin, Ultimate-TTS, NATS, Supabase Storage |
| `P4 UI/Workflow` | Supabase REST/Studio, NATS, UI build/runtime (`npm`/Streamlit/n8n) |
| `P5 Infra/Data` | Docker networks, GHCR auth, runner lanes, secrets/runtime guardrails |
| `P6 Sandbox/R&D` | E2B/BoTZ execution lane, runner lanes, NATS, security hardening |
| `P7 Tokenomics/Geometry` | NATS Geometry Bus, HiRAG/TensorZero, Supabase, Hyperdimensions |

## Per-Submodule Production Matrix
| Submodule | Profile | Gate Pack | Status |
| --- | --- | --- | --- |
| `PMOVES-Agent-Zero` | `P1` | `S + C + R1 + R2` | `pending` |
| `PMOVES-Archon` | `P1` | `S + C + R1` | `pending` |
| `PMOVES-BoTZ` | `P1` | `S + C + R1` | `in-flight` |
| `PMOVES-BotZ-gateway` | `P1` | `S + C + R1` | `in-flight` |
| `PMOVES-crush` | `P1` | `S + C + R1` | `pending` |
| `Pmoves-cipher` | `P1` | `S + C + R1` | `pending` |
| `pmoves/integrations/archon` | `P1` | `S + C + R1` | `pending` |
| `PMOVES-Deep-Serch` | `P2` | `S + C + R1 + R2` | `pending` |
| `PMOVES-HiRAG` | `P2` | `S + C + R1 + R2` | `pending` |
| `PMOVES-Open-Notebook` | `P2` | `S + C + R1` | `baseline-reviewed` |
| `PMOVES-tensorzero` | `P2` | `S + C + R1 + R2` | `pending` |
| `PMOVES-Pipecat` | `P3` | `S + C + R1 + R2` | `baseline-reviewed` |
| `PMOVES-Ultimate-TTS-Studio` | `P3` | `S + C + R1 + R2` | `pending` |
| `PMOVES-Pinokio-Ultimate-TTS-Studio` | `P3` | `S + C + R1 + R2` | `pending` |
| `PMOVES-transcribe-and-fetch` | `P3` | `S + C + R1 + R2 + R3` | `pending` |
| `PMOVES.YT` | `P3` | `S + C + R1 + R2 + R3` | `in-flight` |
| `PMOVES-Jellyfin` | `P3` | `S + C + R1 + R2 + R3` | `in-flight` |
| `Pmoves-Jellyfin-AI-Media-Stack` | `P3` | `S + C + R1 + R2 + R3` | `in-flight` |
| `PMOVES-DoX` | `P3` | `S + C + R1 + R2` | `baseline-reviewed` |
| `PMOVES-Creator` | `P3` | `S + C + R1 + R2` | `pending` |
| `PMOVES-A2UI` | `P4` | `S + C + R1` | `pending` |
| `PMOVES-MAI-UI` | `P4` | `S + C + R1` | `pending` |
| `Pmoves-hyperdimensions` | `P7` | `S + C + R1 + R2` | `baseline-reviewed` |
| `PMOVES-n8n` | `P4` | `S + C + R1 + R4` | `pending` |
| `PMOVES-Wealth` | `P4` | `S + C + R1 + R4` | `pending` |
| `Pmoves-Health-wger` | `P4` | `S + C + R1 + R4` | `pending` |
| `PMOVES-supabase` | `P5` | `S + C + R1` | `pending` |
| `PMOVES-Tailscale` | `P5` | `S + C + R1` | `pending` |
| `PMOVES-Remote-View` | `P5` | `S + C + R1` | `pending` |
| `PMOVES-Headscale` | `P5` | `S + C + R1` | `pending` |
| `PMOVES-ToKenism-Multi` | `P7` | `S + C + R1 + R2` | `pending` |
| `PMOVES-AgentGym` | `P6` | `S + C + R1` | `pending` |
| `Pmoves-AgentGym-RL` | `P6` | `S + C + R1` | `pending` |
| `PMOVES-llama-throughput-lab` | `P6` | `S + C + R1 + R2` | `pending` |
| `PMOVES-surf` | `P6` | `S + C + R1` | `pending` |
| `PMOVES-E2B-Danger-Room` | `P6` | `S + C + R1` | `pending` |
| `PMOVES-E2B-Danger-Room-Desktop` | `P6` | `S + C + R1` | `pending` |
| `PMOVES-Danger-infra` | `P6` | `S + C + R1` | `pending` |
| `PMOVES-E2b-Spells` | `P6` | `S + C + R1` | `pending` |
| `pmoves-e2b-mcp-server` | `P6` | `S + C + R1` | `pending` |

## Deterministic Per-Submodule PR Checklist
For each submodule PR:
- [ ] `make -C pmoves submodule-layer-validate-one SUBMODULE=<submodule-name-or-path>`
- [ ] `make -C pmoves submodule-branch-policy-check`
- [ ] `make -C pmoves submodule-integrity-strict`
- [ ] Run profile runtime gates (`R1`/`R2`/`R3`/`R4`) based on matrix.
- [ ] PR base is `PMOVES.AI-Edition-Hardened-Integrations`.
- [ ] `gh pr checks <pr-number>` reports `integration-gate` as `pass`.
- [ ] No unresolved required review comments.

## Merge Order (Deterministic)
1. `P5` infra/data foundations
2. `P2` knowledge/LLM and `P1` agent-auth lanes
3. `P3` media/voice lanes
4. `P4` UI/workflow lanes
5. `P7` tokenomics/geometry lanes
6. `P6` sandbox/R&D lanes (if included in production scope)
7. Promote `PMOVES.AI-Edition-Hardened-Integrations` -> `PMOVES.AI-Edition-Hardened` -> `main` only after all required checks are green
