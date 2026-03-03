# Submodule Layer Validation
_Generated: 2026-03-03 02:38 UTC_

## Summary
- Manifest: `pmoves/configs/submodule_layer_validation_manifest.json`
- Submodules declared: **40**
- Initialized: **40/40**
- Top-level modules: **39**
- Findings: **0 error(s)**, **0 warning(s)**

## Matrix
| Submodule | Initialized | Status | Remote Commit | Docs(any) | Top-level Dossier | Nested .gitmodules | Python Compile |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `PMOVES-A2UI` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-Agent-Zero` | yes | ` ` | `local` | yes | yes | ok | `pass` |
| `PMOVES-AgentGym` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `Pmoves-AgentGym-RL` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-Archon` | yes | ` ` | `local` | yes | yes | ok | `pass` |
| `PMOVES-BoTZ` | yes | ` ` | `local` | yes | yes | ok | `pass` |
| `PMOVES-BotZ-gateway` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `Pmoves-cipher` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-Creator` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-crush` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-Danger-infra` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-Deep-Serch` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-DoX` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-E2B-Danger-Room` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-E2B-Danger-Room-Desktop` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `pmoves-e2b-mcp-server` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-E2b-Spells` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-Headscale` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `Pmoves-Health-wger` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-HiRAG` | yes | ` ` | `local` | yes | yes | ok | `pass` |
| `Pmoves-hyperdimensions` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-Jellyfin` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `Pmoves-Jellyfin-AI-Media-Stack` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-llama-throughput-lab` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-MAI-UI` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-n8n` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-Open-Notebook` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-Pinokio-Ultimate-TTS-Studio` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-Pipecat` | yes | ` ` | `local` | yes | yes | ok | `pass` |
| `PMOVES-Remote-View` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-supabase` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-surf` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-Tailscale` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-tensorzero` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-ToKenism-Multi` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-transcribe-and-fetch` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-Ultimate-TTS-Studio` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES-Wealth` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `PMOVES.YT` | yes | ` ` | `local` | yes | yes | ok | `skip` |
| `pmoves/integrations/archon` | yes | ` ` | `local` | yes | yes | ok | `skip` |

## Findings
- No findings.

## Layering Guidance
1. Run `make -C pmoves submodule-layer-validate-strict` until this report is clean.
2. Then run `make -C pmoves audit-layers-static` for root/static gates.
3. Finally run `make -C pmoves audit-layers-runtime` once services are up.

