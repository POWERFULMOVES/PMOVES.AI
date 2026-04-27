# PMOVES.AI Sidecar Configuration

## Instance Role
- **Mode**: Sidecar (standalone) — TOPOLOGY_MODE=standalone
- **Parent System**: PMOVES.AI v1.0.0-hardened
- **Hardware**: Any device with Docker — laptop, VPS, workstation, or DGX
- **GPU**: Optional — nvidia-container-runtime if available, CPU-only otherwise

## LLM Providers
- **ollama_local**: Ollama on host via host.docker.internal:11434 (works on any device with Ollama)
- **zai_coding**: GLM-5-turbo via Z.AI MAX plan (chat + utility)
- **tensorzero**: Prepared profile — activate when compose stack is up

## Agent Profiles (agents.json)
- `sidecar`: Default — Ollama local inference on any device
- `tensorzero`: Prepared — TensorZero LLM routing (compose required)
- `researcher`: GLM-5-turbo for research tasks
- `code-reviewer`: GLM-5-turbo for code review

## Deployment Role
The sidecar is the agent interface for deploying PMOVES.AI on new systems.
It uses code_execution_remote for host access and the PMOVES Mini CLI for orchestration.

### Mini CLI Deployment Commands
- `python3 -m pmoves.tools.mini_cli bootstrap --accept-defaults --service agent-zero` — env bootstrap
- `python3 -m pmoves.tools.mini_cli profile_detect` — auto-detect hardware capabilities
- `python3 -m pmoves.tools.mini_cli profile_apply <id>` — apply detected hardware profile
- `python3 -m pmoves.tools.mini_cli credentials_fetch` — pull secrets from GitHub
- `python3 -m pmoves.tools.mini_cli tailscale_authkey` — configure Tailscale networking
- `python3 -m pmoves.tools.mini_cli deps check` — verify host tooling (make, jq, pytest, etc.)

## CHIT Configuration (Dev Mode)
- CHIT_PASSPHRASE: set via env (dev-local-sidecar-override in sidecar.env)
- CHIT_REQUIRE_SIGNATURE: false (dev mode)
- CHIT_DECRYPT_ANCHORS: false (dev mode)
- Flip to true when compose stack is available

## JetStream
- Disabled (AGENTZERO_JETSTREAM=false) — no NATS in standalone mode
- Enable when compose stack provides NATS bus

## Network
- Ollama: http://host.docker.internal:11434 (universal Docker host gateway)
- Host access: code_execution_remote (CLI connector)
- A2A: http://host.docker.internal:5080/a2a/t-TOKEN (token from Settings→MCP/A2A)

## Transition to Docked Mode
When compose stack is available:
1. Set TOPOLOGY_MODE=docked in sidecar.env
2. Set CHIT_REQUIRE_SIGNATURE=true
3. Set CHIT_DECRYPT_ANCHORS=true
4. Set AGENTZERO_JETSTREAM=true
5. Switch to tensorzero agent profile

## Git Operations on Agent Zero Projects

* For project directories containing `.a0proj/project.json`, NEVER run `git checkout`, `git rebase`, `git merge`, or branch switching directly in `/a0/usr/projects/*/` directories
* Use git worktrees in `/tmp/` or separate clones in `/tmp/` for checkout/rebase/merge/branch-switch operations to avoid corrupting Agent Zero project configuration files
* Safe operations on main working directory: `push`, `pull --ff-only`, `fetch`, `status`, `log`, `diff`, `dispatch`
6. Restart container
