# Super CLI Integration Design
**PMOVES Integration Layer: Connecting Agent Zero, Archon, Pinokio, Hermes, Pi Agent, and Warp**

**Date:** 2026-05-20
**Status:** Design Approved
**Type:** Integration & Validation (Not New Development)

---

## Executive Summary

PMOVES has three major systems with existing plugin/skill architectures:
- **Agent Zero** — Orchestration, MCP API (port 8080), NATS event bus
- **Archon** — Agent minting, Supabase integration, strategy retrieval
- **Pinokio P7** — App launcher, agent interpreter, Tailscale mesh

This design creates an **integration layer** that wires these existing systems together, adds missing components (Hermes, Pi CLI, Warp profile), and validates end-to-end functionality.

**Key Principle:** We're connecting dots, not building from scratch. Synthesize only where needed.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   PMOVES Integration Layer                       │
│                 (Wiring + Validation + Testing)                  │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Agent Zero   │    │   Archon     │    │   Pinokio    │
│ MCP API 8080 │   │  Supabase    │    │  P7 Launcher │
│ NATS Bus     │    │  Neo4j       │    │  Tailscale   │
│ Plugins ✓    │    │  Plugins ✓   │    │  Skills ✓    │
└──────────────┘    └──────────────┘    └──────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   NATS Subjects  │
                    │  (Event Bus)     │
                    └──────────────────┘
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  `agent.*`           `archon.*`           `pinokio.*`
  `hermes.*`          `cipher.*`           `pi.*`
```

---

## Component Matrix

| Component | Status | Action Required |
|-----------|--------|-----------------|
| **Agent Zero** | ✓ Existing | Validate NATS wiring, test Archon/Pinokio connectivity |
| **Archon** | ✓ Existing | Connect to Hi-RAG strategy pool, validate minting via NATS |
| **Pinokio P7** | ✓ Existing | Validate mesh discovery, test agent interpreter |
| **Hermes** | ⚠️ Assess | Fork `hermes-mod.git`, integrate as mesh MOF agent |
| **Pi Agent** | ⚠️ Partial | SDK embedded in ClawZ, needs CLI wrapper |
| **Warp** | ⚠️ New | Create PMOVES profile, define workflows |
| **Cipher** | ✓ Existing | Validate cartridge hot-swap via NATS |

---

## Integration Phases

### Phase 1: Validate Existing Wiring

**Goal:** Confirm Agent Zero, Archon, and Pinokio can communicate via NATS.

**Tasks:**
1. Test Agent Zero → Archon connectivity via `archon.*` subjects
2. Test Agent Zero → Pinokio pterm integration
3. Test Archon → Supabase/Neo4j/Hi-RAG queries
4. Test Pinokio → Tailscale mesh discovery (`pmoves-b850-ai-top`)

**Validation Commands:**
```bash
# Agent Zero health
curl -s http://localhost:8080/healthz

# NATS subject check
nats sub ">" --count 10  # Observe all subjects

# Archon minting test
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "archon.mint", "params": {...}}'

# Pinokio P7 discovery
pterm which llama-server
pterm list
```

**Success Criteria:**
- Agent Zero responds to `/healthz`
- NATS messages flow between services
- Archon can query Supabase
- Pinokio discovers installed apps

---

### Phase 2: Assess & Integrate Hermes

**Goal:** Integrate Hermes as a local mesh MOF agent.

**Tasks:**
1. Fork `hermes-mod.git` as submodule: `PMOVES-Hermes/`
2. Assess Hermes customization points (MOF hooks, mesh integration)
3. Wire Hermes to NATS (`hermes.agent.session.v1`, `hermes.mesh.*`)
4. Connect Hermes to Cipher cartridge system

**NATS Subjects:**
```javascript
hermes.agent.session.v1      // Session lifecycle
hermes.mesh.discovery.v1     // Mesh node discovery
hermes.mesh.command.v1       // Cross-node commands
hermes.cartridge.swap.v1     // Hot-swap triggers
```

**Success Criteria:**
- Hermes submodule added and builds
- Hermes publishes to NATS subjects
- Other nodes can discover Hermes via Tailscale
- Cartridge swaps trigger via NATS

---

### Phase 3: Pi Agent CLI Wrapper

**Goal:** Create CLI around existing Pi SDK in PMOVES-ClawZ.

**Current State:** Pi Agent is embedded in `PMOVES-ClawZ/src/agents/` using:
- `@earendil-works/pi-agent-core: 0.74.0`
- `@earendil-works/pi-ai: 0.74.0`
- `@earendil-works/pi-coding-agent: 0.74.0`
- `@earendil-works/pi-tui: 0.74.0`

**Tasks:**
1. Create `pmoves/tools/pi_cli.py` using Typer
2. Wrap existing SDK: `createAgentSession()`
3. Wire to Agent Zero MCP API
4. Add to Super CLI command surface

**Command Surface:**
```bash
pmoves pi chat "Explain HiRAG"
pmoves pi code --file main.py
pmoves pi status
```

**NATS Integration:**
```javascript
pi.agent.command.v1    // Command dispatch
pi.session.start.v1    // Session lifecycle
pi.session.output.v1   // Response streaming
```

**Success Criteria:**
- CLI wrapper responds to commands
- Integrates with Agent Zero MCP
- Publishes session events to NATS

---

### Phase 4: Warp Terminal Profile

**Goal:** Create PMOVES-specific Warp profile and workflows.

**Warp Repository:** `warpdotdev/WARP` (now open source)

**Tasks:**
1. Install Warp on B850 if not present
2. Create PMOVES Warp profile (~/.warp/profiles/pmoves/)
3. Define workflows for: dev operations, mesh status, AI assistance
4. Integrate with pterm shortcuts

**Profile Structure:**
```yaml
# ~/.warp/profiles/pmoves/profile.yaml
name: PMOVES Development
workflows:
  - name: "Start Services"
    commands: ["make -C pmoves up", "pterm start llama-server"]
  - name: "Fleet Status"
    commands: ["tailscale status", "pmoves mesh status"]
  - name: "AI Chat"
    commands: ["pmoves pi chat"]
aliases:
  pmup: make -C pmoves up
  pmdown: make -C pmoves down
  pifi: pmoves pi
```

**Success Criteria:**
- Warp profile loads correctly
- Workflows execute PMOVES commands
- Shortcuts work in terminal

---

### Phase 5: End-to-End Validation

**Goal:** Test full integration across all components.

**Test Scenarios:**

1. **Cartridge Hot-Swap via NATS**
   ```bash
   # Emit swap event
   nats pub cipher.cartridge.swap.v1 '{"name": "voice-mode"}'
   # Verify Pi Agent picks up new context
   pmoves pi chat "What mode am I in?"
   ```

2. **Archon Strategy Retrieval**
   ```bash
   # Query Hi-RAG pool
   pmoves strategies list "retrieval optimization"
   # Mint agent with strategy
   pmoves agent mint --strategy HiRAG-optimized
   ```

3. **Hermes Mesh Operations**
   ```bash
   # Discover Hermes on mesh
   pmoves mesh discover --agent hermes
   # Send cross-node command
   pmoves mesh broadcast --subject hermes.mesh.command.v1
   ```

4. **Full Pipeline Test**
   ```bash
   # Start all services
   pmoves up
   # Verify NATS flow
   nats sub ">" --count 20
   # Test each component
   pmoves pi status
   pmoves hermes status
   pmoves strategies list
   ```

**Success Criteria:**
- All components respond to health checks
- NATS messages flow between services
- Cartridge swaps propagate correctly
- Cross-node commands execute

---

## NATS Subject Catalog

### Agent Zero
```
agent.task.request.v1       // Task dispatch
agent.task.response.v1      // Task results
agent.heartbeat.v1          // Agent heartbeat
```

### Archon
```
archon.mint.agent.v1        // Agent minting requests
archon.strategy.query.v1    // Strategy retrieval
archon.persona.list.v1      // Persona enumeration
```

### Hermes
```
hermes.agent.session.v1     // Session lifecycle
hermes.mesh.discovery.v1    // Node discovery
hermes.mesh.command.v1      // Cross-node commands
```

### Pi Agent
```
pi.agent.command.v1         // Command dispatch
pi.session.start.v1         // Session start
pi.session.output.v1        // Response streaming
```

### Cipher
```
cipher.cartridge.swap.v1    // Hot-swap triggers
cipher.context.get.v1       // Context queries
cipher.context.set.v1       // Context updates
```

### Pinokio
```
pinokio.app.launch.v1       // App launch events
pinokio.app.status.v1       // App status queries
pinokio.agent.session.v1    // Agent session tracking
```

---

## File Structure

```
PMOVES.AI/
├── pmoves/
│   ├── tools/
│   │   ├── pi_cli.py              # NEW: Pi Agent CLI wrapper
│   │   ├── mini_cli.py            # EXISTING: Base CLI framework
│   │   └── supercli_router.py     # NEW: Smart router
│   ├── configs/
│   │   └── nats/
│   │       └── subjects.yaml      # UPDATE: Add Hermes/Pi subjects
│   └── docs/
│       └── superpowers/
│           └── specs/
│               └── 2026-05-20-supercli-integration-design.md  # THIS FILE
├── PMOVES-Hermes/                  # NEW: Hermes submodule
│   └── (hermes-mod.git content)
├── PMOVES-ClawZ/                   # EXISTING: Pi Agent SDK
│   └── src/agents/
│       └── pi/
└── PMOVES-Agent-Zero/              # EXISTING: Orchestration
    └── (Agent Zero content)
```

---

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Agent Zero | v1.3+ | Orchestration, MCP API |
| Archon | Latest | Agent minting, strategies |
| Pinokio | v7.0+ | P7 launcher, mesh |
| NATS | v2.10+ | Event bus |
| Supabase | Latest | Strategy storage |
| Neo4j | Latest | Knowledge graph |
| Typer | Latest | CLI framework |
| Warp | Latest+ | Terminal (optional) |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Hermes fork incompatible | Assess early, create compatibility layer if needed |
| NATS subject collision | Use namespaced subjects, document catalog |
| Pi Agent SDK changes | Pin specific version (0.74.0), monitor upstream |
| Warp not available on B850 | Provide fallback to standard terminal |
| Cartridge swap race conditions | Use NATS ack/retry, version cartridges |

---

## Success Metrics

1. **Integration Coverage:** All 6 components wired and validated
2. **NATS Flow:** Messages flow between all services without loss
3. **Cartridge Swaps:** Hot-swaps complete within 5 seconds
4. **CLI Response:** Commands return within 2 seconds (local), 10 seconds (mesh)
5. **Test Coverage:** End-to-end tests for all critical paths

---

## Next Steps

1. Create implementation plan via `writing-plans` skill
2. Execute Phase 1 (Validate Existing Wiring)
3. Proceed through Phases 2-5 sequentially
4. Document working patterns as they're validated
