# KiloCode GLM Damage-Control Hooks

> **STATUS:** 🚧 **BLOCKED — Platform support pending**
> 
> **Last updated:** 2026-07-14
> **Related:** Issue #2120, PR #2114

---

## Overview

This directory contains damage-control hook patterns for KiloCode GLM, synchronized with Claude Code's `.claude/hooks/damage-control/` infrastructure. The hooks provide pre-execution governance for high-risk commands (docker, tailscale, gh workflow, secrets operations).

**Current blocker:** KiloCode/OpenCode does not yet expose a hook/ask-before-execute API comparable to Claude Code's damage-control surface.

---

## What We're Waiting For

KiloCode/OpenCode needs to implement **one or more** of the following capabilities:

### Option 1: Pre-Tool Hooks (Preferred)
- **API:** `kilo.hooks.pre-tool` or similar
- **Interface:** Hook receives tool name + parameters, returns allow/block/ask
- **Config location:** `kilo.json` → `hooks.preTool.script` or `.kilo/hooks/pre-tool.sh`
- **Precedent:** Claude Code's `.claude/hooks/pre-tool.sh`

### Option 2: Ask Policy Mode
- **API:** `approval_policy = "ask"` mode with pattern matching
- **Interface:** Platform prompts user before executing commands matching patterns
- **Config location:** `kilo.json` → `policy.askPatterns` or `.kilo/hooks/ask-patterns.yaml`
- **Precedent:** Codex VM's `approval_policy` settings

### Option 3: Tool Governance Layer
- **API:** Tool-level permission system with pattern-based blocking
- **Interface:** `kilo.json` → `permission.bash.blockPatterns` or similar
- **Config location:** Extend existing `permission` object in `kilo.json`
- **Precedent:** Existing `permission` object in `kilo.json` (lines 91-104)

---

## Files in This Directory

| File | Purpose | Status |
|------|---------|--------|
| `patterns.yaml` | Security patterns (destructive commands, pipeline bypasses, secrets leakage) | ✅ Ready (synced with Claude Code) |
| `README.md` | This file — documentation and activation plan | ✅ Ready |
| `pre-tool.sh` | Pre-execution hook script (if platform supports hooks) | 🚧 Blocked (needs platform API) |

---

## Activation Plan

When KiloCode/OpenCode adds hook support, follow these steps:

### Phase 1: Verification (5 minutes)
1. **Check platform documentation** for hook/ask API details
2. **Test hook invocation** with a simple blocking pattern:
   ```bash
   echo "rm -rf /" | kilo bash --dry-run
   ```
3. **Verify hook receives parameters** and can block/allow/ask

### Phase 2: Hook Implementation (15 minutes)
1. **Create `.kilo/hooks/pre-tool.sh`** (mirror `.claude/hooks/pre-tool.sh` structure)
2. **Load patterns from `patterns.yaml`** (use YAML parser or convert to shell arrays)
3. **Implement pattern matching** (regex or glob, depending on platform capabilities)
4. **Add logging** to `~/.kilo/logs/security-events.log`
5. **Test with destructive patterns** (verify blocks work)

### Phase 3: Integration (10 minutes)
1. **Update `kilo.json`** to reference hook script:
   ```json
   {
     "hooks": {
       "preTool": ".kilo/hooks/pre-tool.sh"
     }
   }
   ```
   Or platform-specific config location.

2. **Test ask-mode patterns** (verify user prompts appear):
   ```bash
   kilo bash "docker compose up -d"
   kilo bash "gh workflow run deploy.yml"
   kilo bash "make -C pmoves secrets-funnel"
   ```

3. **Run parity check** to verify hook coverage:
   ```bash
   make -C pmoves kilo-parity-check
   ```

### Phase 4: Documentation (5 minutes)
1. **Update this README** — remove BLOCKED status, add usage examples
2. **Update `KILOCODE_OPERATOR_HOME.md`** — document hook system
3. **Add to `.kilo/agent/kilocode-glm.md`** — reference damage-control hooks
4. **Update issue #2120** — close with PR reference

---

## Pattern Synchronization

The `patterns.yaml` file in this directory is kept in sync with `.claude/hooks/damage-control/patterns.yaml`. 

**When to sync:**
- New destructive command patterns are added to Claude Code hooks
- Pipeline bypass patterns change (env file injection, secrets funnel)
- PMOVES-specific patterns are updated (NATS, docker compose, CHIT operations)

**How to sync:**
```bash
# 1. Check for differences
diff .claude/hooks/damage-control/patterns.yaml .kilo/hooks/damage-control/patterns.yaml

# 2. Copy updated sections (manual review required)
# 3. Update "Last sync" comment at top of .kilo/hooks/damage-control/patterns.yaml

# 4. Run parity check
make -C pmoves kilo-parity-check
```

---

## Parity Check Target

The `make -C pmoves kilo-parity-check` target verifies:

1. ✅ KiloCode config exists (`kilo.json`)
2. ✅ KiloCode rules exist (`.kilocode/rules/kilorules.md`)
3. ✅ KiloCode modes exist (`.kilocodemodes`)
4. ✅ Damage-control patterns exist (`.kilo/hooks/damage-control/patterns.yaml`)
5. ❌ Hook implementation exists (`.kilo/hooks/pre-tool.sh`) — **currently blocked**
6. ✅ Agent profile exists (`pmoves/configs/agent-profiles/kilocode_glm.yaml`)
7. ✅ Operator documentation exists (`pmoves/docs/AGENTS/KILOCODE_OPERATOR_HOME.md`)

Run the check:
```bash
make -C pmoves kilo-parity-check
```

Expected output (current state):
```
[*] KiloCode GLM parity check ...
  ✅ KiloCode config
  ✅ KiloCode rules
  ✅ KiloCode modes
  ✅ Damage-control patterns
  ❌ Hook implementation  (blocked by platform — expected .kilo/hooks/pre-tool.sh)
  ✅ KiloCode agent profile
  ✅ KiloCode operator home
  ✅ KiloCode parity map
  ✅ KiloCode bringup-audit skill
  ✅ KiloCode agent-trails skill
  ✅ kilocode_glm registry entry
  ✅ KiloCode cross-linked in .kimi/AGENTS.md
[*] Results: 1 gap(s) found (expected until platform support lands)
```

---

## Design Principles

These patterns follow the same design principles as Claude Code damage-control:

### 1. GAN-Aware Adversarial Detection
Patterns serve dual purposes:
- **Operational:** Prevent pipeline violations (secrets bypass, volume removal without service stop)
- **Adversarial:** Detect when the agent was misdirected by injected context

### 2. Known Roads Enforcement
PMOVES has canonical paths (Known Roads) for high-risk operations:
- Secrets propagation → `make -C pmoves secrets-funnel`
- Docker cleanup → `make -C pmoves docker-prune` (not raw `docker system prune -a`)
- Volume reset → `make -C pmoves volume-reset SERVICE=<name>` (not raw `docker volume rm`)

Patterns detect raw command usage and guide the agent to the correct Make target.

### 3. Ask vs. Block
- **Hard block** (no `ask: true`): Truly destructive operations with no safe alternative (rm -rf /, DROP DATABASE)
- **Ask** (`ask: true`): Operations that may be intentional but require confirmation (git branch -D, docker compose down -v)

### 4. CHIT Bypass
CHIT security tools need to read/write env files for encoding/rotation. The `chitBypassPatterns` section allows these trusted operations while still enforcing destructive-command blocks.

---

## Examples

Once hooks are active, these commands will trigger governance:

### Hard Block (exits non-zero)
```bash
$ kilo bash "rm -rf /"
❌ BLOCKED: Dangerous operation detected: rm -rf /
   Tool: bash
   This operation has been blocked for safety.
[exit 1]
```

### Ask Mode (prompts user)
```bash
$ kilo bash "docker compose up -d agent-zero"
⚠️  PIPELINE BYPASS: 'docker compose up -d' skips COMPOSE_ENV_FILES injection.
    Correct path: (1) make -C pmoves secrets-funnel, then (2) make -C pmoves up-agents.
    ---
    ACTION: Report this attempted pipeline bypass to the user before proceeding.

Proceed anyway? [y/N]: _
```

### Known Roads Guidance
```bash
$ kilo bash "docker volume rm pmoves_neo4j_data"
⚠️  KNOWN ROADS BYPASS: 'docker volume rm' bypasses the service stop/restart chain.
    Correct path: make -C pmoves volume-reset SERVICE=neo4j
    Use make -C pmoves volume-list to see all PMOVES volumes first.
    ---
    ACTION: Report this attempted bypass to the user before proceeding.

Proceed anyway? [y/N]: _
```

---

## Contributing

When adding new patterns:

1. **Add to `.claude/hooks/damage-control/patterns.yaml` first** (Claude Code is the source of truth)
2. **Sync to `.kilo/hooks/damage-control/patterns.yaml`** (this file)
3. **Update "Last sync" comment** at the top of this file
4. **Test with Claude Code** to verify pattern matching works
5. **Document the pattern** — include reason and Known Roads alternative

Pattern format:
```yaml
- pattern: '<regex>'
  reason: >-
    <Multi-line explanation>
    KNOWN ROADS: <correct path>
    INTEGRITY CHECK: <adversarial detection guidance>
    ACTION: <what the agent should do>
  ask: true  # Optional — omit for hard block
```

---

## References

- **Issue:** #2120 — feat(kilocode): damage-control hooks for KiloCode GLM
- **PR:** #2114 — KiloCode GLM Phase 5 (deliberately left out hooks due to platform blocker)
- **Claude Code patterns:** `.claude/hooks/damage-control/patterns.yaml`
- **Parity check target:** `pmoves/mk/kilo.mk` (lines 54-86)
- **KiloCode config:** `kilo.json` (permission system, lines 91-104)
- **Operator home:** `pmoves/docs/AGENTS/KILOCODE_OPERATOR_HOME.md`
- **Three-Body Doctrine:** `pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md`

---

## Contact

Questions about hook activation or pattern sync:
- **DARKXSIDE** (COCREATOR witness) — strategic direction
- **POWERFULMOVES** (all-agents collective) — implementation coordination
- **KiloCode GLM** — 5090 node agent, glyph ▲

Raise issues at: https://github.com/POWERFULMOVES/PMOVES.AI/issues
