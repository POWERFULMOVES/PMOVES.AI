# PR 1/5: feat(hermes-profile): Ageless Beauty practice workstation profile

> **Practice Context**: This profile serves a Nurse Practitioner with her own practice (Ageless Beauty).
> The workstation must balance clinical workload (HIPAA-aware) with PMOVES.AI development.
> Cloud-first model strategy conserves local GPU for patient data embeddings.

## Type
- [x] feat
## Scope
hermes-profile
## Description
Adds the Elder-Melchor node profile as the **Ageless Beauty practice workstation**.
- Nurse Practitioner clinical workflow integration
- HIPAA-compliant patient data handling (auto-redact)
- Cloud-first inference (Z.AI + MiniMax primary, Ollama cloud/remote)
- Hostinger website hosting configuration
- BPM Three-Layer Bridge Architecture (FULL):
  - BPM¹ Beats Per Minute: Flute Gateway prosodic TTS, ToKenism beat-sync
  - BPM² Bridge Protocol Module: CHIT geometry bus, hyperdimensional encoding
  - BPM³ Business Process Management: Ageless Beauty practice workflows
- PMOVES Health/Wealth stack integration (planned)

## Node Impact
- [x] elder-melchor (Ageless Beauty practice workstation)
- [x] z890 (restored as separate PMOVES dev node)

## Provider Hierarchy (Practice-Optimized)
| Tier | Provider | Use Case |
|------|----------|----------|
| 1 | Z.AI Coding Plan | Code generation, documentation, PR review |
| 2 | MiniMax Token Plan | Creative content, patient education materials |
| 3 | Ollama Cloud | Remote model serving (NOT local GPU) |
| 4 | OpenRouter | General fallback |
| 5 | Kimi / Alibaba | Long-context, Chinese-language tasks |
| 6 | Spark / 5090 | Fleet offload for 70B or GPU-heavy |

## Files Changed
- `pmoves/config/profiles/hermes/elder-melchor.yaml` (NEW)
- `pmoves/config/profiles/hermes/z890.yaml` (RESTORED)
- `pmoves/config/profiles/hermes/README.md` (UPDATED)
- `pmoves/config/profiles/hermes/z890-glances.conf` (NEW)
- `pmoves/config/profiles/hermes/elder-melchor-system-specs.json` (NEW)

## Checklist
- [x] Atomic commit (one concern: practice workstation profile)
- [x] Live scan attached (elder-melchor-system-specs.json)
- [x] CHIT signed (pending)
- [x] Glances config created
- [x] Provider hierarchy with practice-optimized tiers
- [x] HIPAA auto-redact configured
- [x] Hostinger hosting notes added
