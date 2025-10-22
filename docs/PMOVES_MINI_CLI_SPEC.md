% PMOVES Mini CLI – Draft Specification
% Updated: 2025-10-21

# 1. Goals

- Provide a single, self-service command-line interface (`pmoves mini …`) that unifies environment setup, hardware-aware bring-up, MCP tooling, CHIT secret management, and agent delegation (Codex / Crush / ASO).
- Reduce cognitive load by collapsing the current collection of Make targets and scripts into guided workflows with validation and status reporting.
- Enable “mini PMOVES” deployments on heterogeneous hardware (desktop GPU rigs, laptops, Jetson edge devices, microcontrollers) with open-source model bundles sized to available resources.
- Ship with preconfigured MCP tools (Docker MCP toolkit, Supabase, Archon, etc.) so higher-level agents can perform privileged operations through an audited channel.
- Keep CHIT CGP secrets as the source of truth and expose friendly commands for encoding/decoding, diffing, and handing off bundles.

# 2. Command Surface (Typer-Based)

```
pmoves mini [GLOBAL OPTIONS] COMMAND [ARGS...]

Core:
  bootstrap          # env bootstrap + provisioning bundle staging
  init                # secrets sync + env generation + profile detection
  status              # aggregate readiness (env, MCP, compose, models)
  profile detect      # inspect hardware, suggest profile
  profile apply       # set active profile (writes ~/.pmoves/profile.yaml)
  bring-up STACK      # start compose stacks (core, agents, external, edge)
  tear-down STACK     # stop stacks matching profile overrides
  models pull|start   # manage open-source model bundles per profile
  secrets encode|decode|diff  # CHIT helpers wrapping existing tools
  agents exec         # delegate task to Codex / Crush / ASO with MCP context
  agents request      # prepare SOS packet for human-approved escalation
  mcp setup           # install/verify MCP toolkits (docker, compose, host ops)
  mcp list            # show active MCP servers and auth status
  crush setup|status|preview # manage Crush configuration tuned for PMOVES
```

Global options include `--profile`, `--non-interactive`, and `--manifest PATH`.

`bootstrap` wraps `pmoves.scripts.bootstrap_env` and stages the provisioning PR
pack (defaulting to `CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/`) so remote bring-up
bundles are ready immediately after secrets populate.

# 3. Architecture Overview

| Layer                   | Responsibilities |
| ----------------------- | ---------------- |
| CLI (Typer app)         | Parse commands, route to service modules, render rich output. |
| Profiles (`config/profiles/*.yaml`) | Describe hardware capabilities, compose overrides, model bundles, MCP adapters, CHIT scope. |
| Secrets Layer           | Reuse `pmoves.tools.secrets_sync` and `pmoves.tools.onboarding_helper`. |
| MCP Integration         | YAML manifest of MCP servers (`config/mcp/*.yaml`) + runner that ensures Docker MCP toolkit is installed and reachable. |
| Agents Bridge           | Task schema (`tasks/*.yaml`), connectors to Codex/Crush/ASO with project-aware system prompts. |
| Model Bundles           | Scripts under `tools/models/` to pull/start Ollama, whisper.cpp, vLLM, TRT-LLM, etc. |

# 4. Hardware Profile Schema (YAML)

```yaml
id: desktop-9950xd
description: AMD 9950XD + RTX 5090 workstation
hardware:
  cpu:
    vendor: AMD
    cores: 16
    threads: 32
  gpu:
    type: nvidia
    models: [RTX 5090]
    memory_gb: 32
  ram_gb: 192
  tags: [desktop, high-end, cuda, local-llm]
compose_overrides:
  - docker-compose.gpu.yml
model_bundles:
  - ollama-high
  - reranker-qwen-large
  - whisper-medium
mcp:
  - docker
  - compose
  - host-controls
chit_scope:
  include_labels:
    - SUPABASE_*
    - MEILI_*
    - DISCORD_*
    - LOCAL_MODEL_*
```

Other profiles will mirror this structure (`laptop-4090`, `intel-265kf-3090ti`, `jetson-nano-edge`, `esp32-sonatino`), including device-specific requirements (Jetson: `sudo systemctl enable nvargus-daemon`, CSI camera setup; ESP32: serial flashing helpers).

# 5. MCP Toolkit Integration

- Bundle manifest: `config/mcp/docker.yaml`, `config/mcp/host.yaml` describing command endpoints, auth, and readiness checks.
- `pmoves mini mcp setup`:
  1. Verify Docker CLI and socket access.
  2. Install/update Docker MCP toolkit (likely via `pip install mcp-docker` or containerized distribution).
  3. Register tools with local agent config (`~/.pmoves/mcp/registry.json`).
- MCP readiness is part of `status`: check handshake with each server, confirm credentials exist in CHIT manifest (new labels `MCP_DOCKER_TOKEN`, etc.).

# 6. CHIT CLI Operations

Reuse existing encode/decode modules with friendlier names:

```
pmoves mini secrets encode --out pmoves/pmoves/data/chit/env.cgp.json
pmoves mini secrets decode --out /tmp/env.decoded
pmoves mini secrets diff --bundle other.cgp.json
pmoves mini secrets rotate --label SUPABASE_SERVICE_ROLE_KEY
```

All commands funnel through `secrets_sync` so generated env files stay consistent. `rotate` will update manifest entries, regenerate CGP, and prompt the user for new values (leveraging the onboarding helper prompt flow).

# 7. Agent Delegation

- Provide system prompt template containing:
  - Repository context (ROADMAP/NEXT_STEPS highlights).
  - Active profile details (so agent knows which hardware/service is available).
  - MCP toolkit summary + credentials.
  - Constraints from the Codex CLI harness.
- Tasks defined as YAML (e.g., `tasks/restart_archon.yaml`) with fields `description`, `commands`, `permission_level`, `expected_output`.
- `pmoves mini agents exec --tool crush --task restart_archon` uploads context to the tool’s API, streams live output to user.
- `agents request` generates an SOS bundle with logs, env diffs, and instructions—suitable for human review before executing privileged commands outside the sandbox.

# 8. Implementation Roadmap

1. **Spec & Docs (this document)** → ensure shared understanding.
2. **CLI Skeleton**
   - Add `pmoves/tools/mini_cli.py` (Typer).
   - Implement `init`, `status`, `profile detect`, `secrets encode/decode` using existing helpers.
   - Hook into Makefile (`make mini …`) for convenience.
3. **Profiles & Detection**
   - Create `config/profiles/*.yaml`.
   - Hardware detector module (CPU/GPU/Jetson/ESP32).
   - Persist selected profile to `~/.pmoves/profile.yaml`.
4. **MCP Integration**
   - Add `config/mcp/*.yaml`.
   - Implement `mcp setup|list` with validation.
   - Update status command to include MCP readiness.
5. **Model Bundles**
   - Define scripts for model pull/start per profile.
   - Manage process supervision (e.g., `supervisord` or compose sidecars).
6. **Agent Bridge**
   - Implement connectors to Codex/Crush/ASO APIs.
   - Support streaming output and audit logs.
7. **Edge Profiles**
   - Jetson-specific automation (CSI camera bring-up).
   - ESP32 toolchain integration (esptool flashing, gRPC bridge).
8. **Testing & Docs**
   - CLI unit tests (Typer + pytest).
   - Integration tests for secrets generation & MCP detection.
   - Update `docs/LOCAL_DEV.md`, `docs/SECRETS.md`, add quickstart tutorial.

# 9. Open Questions

- Confirm distribution channel (PyPI package vs in-repo script).
- Define authentication mechanism for Codex/Crush when run outside Codex CLI harness (token handoffs, secure storage).
- Decide whether `pmoves mini` replaces or wraps Make targets long-term.
- Validate legal/licensing considerations for bundling certain open-source models by default.
- Determine telemetry/analytics (if any) for CLI usage—respect privacy requirements.

# 10. Next Steps

1. Review and approve this spec.
2. Begin CLI scaffolding (phase 2 above).
3. Populate initial hardware profile YAMLs and detection logic.
