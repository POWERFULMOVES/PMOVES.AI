# AGNOTE: PMOVES-MISSLING-LINK Onboarding

## Node: pmoves-missling-link
- **Hardware**: Intel Core i7-7700HQ @ 2.80GHz (4 cores / 8 threads, Kaby Lake mobile)
- **Memory**: 16 GB RAM
- **GPU**: NVIDIA GeForce GTX 1070, 8 GB GDDR5 (Pascal, sm_61, driver 546.33)
- **Disk**: D: 48 GB free (PMOVES.AI checkout lives here)
- **OS**: Windows 11 Pro
- **Role**: Dev + light-GPU node — small/quantized model inference, CPU dev/ops, **Hermes Agent gateway host**
- **Agent Runtime**: **Hermes Agent** (Nous Research, v0.17.0) — distinct from the Claude Code / Codex / KiloCode agents on other nodes
- **Access**: Tailscale enrollment TBD (operator); local operator access via Windows
- **Provider**: Hermes `pmoves` profile (cwd pinned to `D:/POWERFULMOVES/PMOVES.AI`), MiniMax-M3 inherited from default (switchable via `pmoves model`)
- **Default Model**: switchable — GLM (coding), Claude (review), MiniMax (token/writing), local Ollama (offline)
- **Agent Identity**: `missling-link` (signing card `00000000-0000-4000-8000-000000000013`, h-only pending operator SSH key)
- **Skill**: `pmoves-convergence` installed (Hermes-native AGNOTE4482 protocol translation)

## Capacity Notes

This is a **legacy laptop-class / light-GPU dev node**, not an inference workhorse:

- The GTX 1070 is **Pascal (sm_61, 2016)** — predates modern capabilities. It can run small/quantized models (llama.cpp GGUF, Ollama with `Q4` 7B-class models) but **cannot** use BF16/FP8 and is unsuitable for large-model inference that the 5090/SPARK nodes handle.
- 16 GB RAM + 4c/8t CPU bounds concurrent container count — treat as a dev/edge node, not a full-stack host like Z890.
- Best-fit lanes: **docs, CI helper, Hermes gateway/ops, lightweight local inference, review/trim work, PR triage**. Avoid heavy `docker compose up` full-stack loads.

## Status
- ✅ Hardware scanned (CIM + nvidia-smi) — values verified
- ✅ Hermes `pmoves` profile created (cwd pinned to project, skill + memory installed)
- ✅ Node-capacity row added to `AGNOTE4482_SITREP.md`
- ✅ Signing identity card seeded (h-only, `00000000-0000-4000-8000-000000000013`)
- ⏳ Tailscale enrollment (operator) — mesh access pending
- ⏳ SSH key on host → `ssh_fingerprint` back-fill in `signing_identity_cards.yaml` (Owner-Decision A)
- ⏳ CI runner registration (optional — only if this node should pick up GitHub Actions jobs)
- ⏳ Capacity-class validation under load (advisory)

## Near-Term Lane
1. Operator: enroll PMOVES-MISSLING-LINK in Tailscale mesh; record the node tag in fleet topology (`pmoves/docs/operations/TOPOLOGY.md`).
2. Operator: generate SSH key on host (`ssh-keygen`), back-fill `signing_identity_cards.yaml:ssh_fingerprint` for card `…0013`.
3. Optional: register a self-hosted GitHub Actions runner on this node if CI overflow is wanted (legacy GPU labels e.g. `self-hosted, missling-link, gpu, pascal`).
4. Optional: local Ollama smoke — pull a Q4 7B model, confirm GTX 1070 offload (`nvidia-smi` shows VRAM use).
5. When emitting trail entries: this node signs as `ACK::MISSING-LINK-HERMES::<SCOPE>`; audit (`audit_naming_drift.py`) will now find an active card for `missling-link`.

## Relationship to W0 Substrate Lane
This onboarding continues the **W0 Substrate — Cross-Platform Node Onboarding** lane (Z890-CLAUDE, 2026-05-09; brief at `AGNOTE4482PHI.W0-SUBSTRATE.md`). The hardware-scan + profile-YAML pattern landed here is a concrete instance of that brief's PR-3 (Windows companion) direction. This node is a candidate test-validation node for the W0 substrate work given it is a fresh Windows system joining the fleet.

Added: 2026-06-23
