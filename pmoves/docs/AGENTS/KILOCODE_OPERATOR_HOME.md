# KiloCode Operator Home

> **Cold-start runbook for KiloCode GLM on the 5090 node.**
> Mirror of `CODEX_OPERATOR_HOME.md` — the canonical model for non-Claude agent integration.

**Glyph:** ▲ (Triangle) | **Color:** #059669 (Emerald) | **Voice:** architectural
**Node:** pmoves-5090 (GPU inference specialist)
**Model:** GLM-5-Turbo via Z.AI Coding Plan (`zai/glm-5-turbo`, fallback `glm-5.1`)
**Co-author:** KiloCode <noreply@kilocode.ai>

---

## Identity

KiloCode GLM is the VS Code-native agent on the 5090 GPU node. It operates alongside Claude Code and Codex on the same machine, sharing the Tailscale mesh and GPU resources.

**Three-Body role:** Delivery Body (implementation lane)
**COCREATOR witness:** DARKXSIDE ✦ — all trail entries carry dual attribution: `DARKXSIDE x POWERFULMOVES on 5090`

---

## Ecosystem Traversal Order

Read these in order on a cold start:

1. **Operator lane:** this file + `.kilo/agent/kilocode-glm.md`
2. **Service map:** `.claude/CLAUDE.md` + `.claude/CATALOG.md`
3. **Submodule map:** `.claude/context/submodules.md`
4. **Skills:** `.kilocode/skills/` + `skills/README.md`
5. **Memory path:** Cipher Memory at `http://localhost:8105/mcp/sse` (or `http://${TS_Z890}:8105/mcp/sse` remote)
6. **Coordination:** `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (Active Claim Register)

---

## Runtime Protocol

### Starting a Session

1. **Check active claims** in `AGNOTE4482PHI.t1.md` — never edit a branch with an open claim from another agent
2. **Disclose Emperor-CHIT-Humility** — state what you have vs. what's missing (Cipher MCP, A2A, Known Roads, CHIT passphrase)
3. **Verify node identity** — confirm you're on 5090 with GPU access:
   ```bash
   nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader
   ollama list
   ```
4. **Check TensorZero health:**
   ```bash
   curl -sf http://localhost:3030/health
   ```

### Claiming Work

Use the `/claim` command or write directly to `AGNOTE4482PHI.t1.md`:

```text
<ISO-8601-timestamp> CLAIM `KILOCODE-GLM` scope: <description>.
  branch: `<name>`. pr_numbers: [#<n>].
  risks: <risks>.
  agent_signature: `ACK::KILOCODE-GLM::<SCOPE>`.
  Three-body: delivery=KILOCODE-GLM, control=DARKXSIDE, memory=this trail.
```

### Working

During implementation, update progress in PR comments and the AGNOTE board:

1. If CI fails, compare the failure against `main` before calling it branch-specific.
2. Keep changes atomic — if you find adjacent cleanups, open a follow-up; don't expand the current claim.
3. Post progress updates to the PR with current blocker state.

### Handoff (Cross-Agent Lane Transition)

When handing off to another agent (Claude, Codex, etc.), emit a KRISS KROSS handshake block AND export a CHIT payload. **All cross-agent handoffs must be posted as CHIT payload references, never plaintext secrets.**

Required handoff fields (8 fields, mandatory):

```text
graphiti_mark:    <trail identifier>
branch:           <git branch name>
pr_numbers:       [#<n>]
scope:            <work scope description>
risks:            <known risks>
next_actions:     <next steps for receiving agent>
chit_artifact_path: <CHIT payload reference — never plaintext>
agent_signature:  <signed ACK block>
```

Export CHIT payload with no cleartext before handoff:

```bash
make -C pmoves chit-export CHIT_NO_CLEARTEXT=1
make -C pmoves chit-manifest-sync
make -C pmoves secrets-funnel-sync
```

Optional CLI path:

```bash
python -m pmoves.tools.mini_cli secrets encode --no-cleartext
```

### Releasing Work

After work is complete and handoff (if any) is done, write RELEASE entry and clear the claim:

```text
<ISO-8601-timestamp> RELEASE `KILOCODE-GLM` scope: <description>.
  branch: `<name>`. pr_numbers: [#<n>].
  next_actions: <actions>.
  agent_signature: `ACK::KILOCODE-GLM::<SCOPE>-RELEASE`.
```

Then sign the trail:

```bash
make -C pmoves sign-trail SUMMARY="<summary>" AGENT="kilocode" PHASE="<phase>"
```

### Trail Signing

Sign the trail for session-end provenance. Signing is optional locally (unsigned if `CHIT_PASSPHRASE` unset) but never skipped for session-end:

```bash
make -C pmoves sign-trail SUMMARY="<summary>" AGENT="kilocode" PHASE="<phase>"
```

---

## Multi-Agent Coordination

### 5090 Node Siblings

| Agent | Tool | Mode | Role |
|-------|------|------|------|
| **KiloCode GLM** ▲ | VS Code + KiloCode | `pmoves-glm` | Blueprint-first implementation |
| **Claude Code** ◆ | Claude CLI | `claude-opus`/`claude-sonnet` | Analysis, architecture, field briefs |
| **Codex** ■ | Codex CLI | `never-approve` | Terse code generation, integration |

### KRISS KROSS Handshake

For cross-agent lane transitions, emit:

```text
KRISS-KROSS-HANDSHAKE
from_agent=kilocode-glm
to_agent=<destination>
branch=<branch>
scope=<scope>
collision_risk=low|medium|high
fallback_mode=ff|overlay|three_way
graphiti_ref=<trail-ref>
chit_ref=<chit-ref>
```

### DARKXSIDE Witness

All trail entries must carry:
- `▲ KiloCode GLM` as implementer
- `✦ DARKXSIDE` as witness
- Source line: `DARKXSIDE x POWERFULMOVES on 5090`

---

## Model Configuration

| Model | Role | Context | Provider |
|-------|------|---------|----------|
| `glm-5-turbo` | Primary — agentic, tool-calling | 128K/32K eff | Z.AI Coding Plan |
| `glm-5.1` | Fallback — long-horizon | 204K/128K eff | Z.AI Coding Plan |
| `glm-4-air` | Edge — fast/cheap | 32K | Z.AI Coding Plan |
| `glm-5v-turbo` | Vision + coding | 128K | Z.AI Coding Plan |
| `kilo-auto/balanced` | Overflow — plan-routed | Variable | KiloCode API |

### TensorZero Routing

| Function | Primary Variant | Weight |
|----------|----------------|--------|
| `coding_glm` | `cloud_zai_turbo` | 0.8 |
| `coding_kilocode` | `cloud_zai_turbo` | 0.8 |
| `agent_zero` | `hosted_zai_turbo` | 0.6 |
| `pmoves_orchestrator_coding` | `cloud_zai_glm51` | 1.0 |
| `pmoves_orchestrator_coding` | `cloud_kilocode` | 0.3 |

---

## MCP Servers

| Server | Purpose | Configured In |
|--------|---------|---------------|
| `zai-vision` | GLM vision analysis, OCR, UI-to-code | `kilo.json` |
| `zai-web-search` | LLM-optimized web search | `kilo.json` |
| `zai-web-reader` | URL content extraction | `kilo.json` |
| `zai-zread` | GitHub repo search/reading | `kilo.json` |
| `docker` | Container management | `kilo.json` |
| `pmoves-cipher` | Persistent agent memory (Neo4j) | `kilo.json` |
| `tailscale` | Tailnet inventory, node cleanup, ACL | `kilo.json` |
| `huggingface` | Model/dataset/spaces search | `kilo.json` |

---

## Z890 Remote Services (via Tailscale)

| Service | URL | Purpose |
|---------|-----|---------|
| Agent Zero | `http://${TS_Z890}:8080` | Orchestrator (MCP API) |
| Archon | `http://${TS_Z890}:8091` | Agent service |
| TensorZero | `http://${TS_Z890}:3030` | LLM gateway |
| NATS | `nats://${TS_Z890}:4222` | Message bus |
| Cipher Memory | `http://${TS_Z890}:8105/sse` | Agent memory (MCP SSE) |
| Ollama (Z890) | `http://${TS_Z890}:11434` | Z890 model serving |

---

## Health Commands

```bash
# GPU
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader

# Local models
ollama list

# Containers
docker ps --format "table {{.Names}}\t{{.Status}}"

# Remote services (via Tailscale)
curl -sf http://${TS_Z890}:8080/healthz   # Agent Zero
curl -sf http://${TS_Z890}:3030/health    # TensorZero
curl -sf http://${TS_Z890}:8105/health    # Cipher Memory

# Fleet
make -C pmoves fleet-status
```

---

## Reference Files

| File | Purpose |
|------|---------|
| `.kilo/agent/kilocode-glm.md` | Agent identity definition |
| `pmoves/config/agent_signatures.yaml` | Glyph ▲, color #059669 (line ~36) |
| `pmoves/configs/claws/opencode-5090.json` | KiloCode node config |
| `pmoves/configs/claws/scopes/5090.json` | Exec approvals and MCP servers |
| `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` | Claim/release protocol |
| `pmoves/docs/AGENTS/KRISS_KROSS_ACCORD.md` | Collision-safe traversal |
| `pmoves/docs/AGENTS/KRISS_KROSS_ACK.md` | DARKXSIDE attestation |
| `pmoves/docs/AGENTS/DARKXSIDE_SIGNATURE.md` | COCREATOR witness protocol |
| `pmoves/tools/models/kilocode_provider_cascade.yaml` | Provider cascade |
| `pmoves/configs/model-suits/glm-5-turbo.yaml` | GLM-5-Turbo suit |
| `pmoves/configs/agent-profiles/kilocode_glm.yaml` | Agent profile |
| `pmoves/docs/AGENTS/KILOCODE_CLAUDE_PARITY_MAP.md` | Command parity map |

---

## ACK

- Agent: `KILOCODE-GLM`
- Signature: `ACK::KILOCODE-GLM::OPERATOR-HOME`
- Timestamp: 2026-07-12
- DARKXSIDE ✦ witness
