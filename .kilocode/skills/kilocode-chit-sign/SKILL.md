---
name: kilocode-chit-sign
description: Sign Graphiti trail entries with DARKXSIDE COCREATOR witness attribution for PMOVES.AI. Use when completing work items, signing trail entries, or performing agent handoffs on the 5090 node.
keywords: [chit, sign, trail, graphiti, darkxside, witness, handoff]
version: 1.0.0
category: PMOVES/KiloCode-GLM
---

# KiloCode CHIT Sign

Graphiti trail signing with DARKXSIDE ✦ COCREATOR witness attribution for KiloCode GLM ▲ on the 5090 node.

## Purpose

Sign trail entries with the correct dual attribution: KiloCode GLM as implementer, DARKXSIDE as
COCREATOR witness. All trail entries from the 5090 carry: `DARKXSIDE x POWERFULMOVES on 5090`.

## Capabilities

- ✍️ Sign Graphiti trail entries with `make -C pmoves sign-trail`
- ✦ Apply DARKXSIDE COCREATOR witness attribution
- 📝 Format claim/release entries for AGNOTE4482PHI.t1.md
- 🤝 Generate KRISS KROSS handshake blocks for cross-agent handoffs
- 🔐 Reference CHIT payload paths (never plaintext secrets)

## Integration Points

- **Trail Signing**: `make -C pmoves sign-trail`
- **Claim Register**: `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`
- **KRISS KROSS Accord**: `pmoves/docs/AGENTS/KRISS_KROSS_ACCORD.md`
- **DARKXSIDE Signature**: `pmoves/docs/AGENTS/DARKXSIDE_SIGNATURE.md`
- **Cipher MCP**: `http://localhost:8105/mcp/sse` — for memory persistence

## Attribution Format

### Trail Entry Header
```
<!-- graphiti:kilocode phase:{phase} ts:{ISO-8601} -->
```

### Signature Block
```
### Agent ACK
- Agent: `KILOCODE-GLM`
- Signature: `ACK::KILOCODE-GLM::<SCOPE>`
- Timestamp: <ISO-8601>
- DARKXSIDE ✦ witness: `DARKXSIDE x POWERFULMOVES on 5090`

<!-- GRAPHITI_MARK: KILOCODE-GLM::<SCOPE>::<date> -->
```

### Three-Body Declaration
```
Three-body: delivery=KILOCODE-GLM ▲, control=DARKXSIDE ✦, memory=this trail.
```

## Workflow

### Step 1: Sign Trail

```bash
make -C pmoves sign-trail SUMMARY="<one-line summary>" AGENT="kilocode" PHASE="<phase>"
```

### Step 2: Add AGNOTE Entry

```markdown
### Agent ACK
- Agent: `KILOCODE-GLM`
- Signature: `ACK::KILOCODE-GLM::<SCOPE>`
- Timestamp: <ISO-8601>
- Branch: `<branch>`
- Three-body: delivery=KILOCODE-GLM, control=DARKXSIDE, memory=this trail.

<!-- GRAPHITI_MARK: KILOCODE-GLM::<SCOPE>::<date> -->
```

### Step 3: Release Claim

```
<ISO-8601> RELEASE `KILOCODE-GLM` scope: <description>.
  branch: `<name>`. pr_numbers: [#<n>].
  next_actions: <actions>.
  agent_signature: `ACK::KILOCODE-GLM::<SCOPE>-RELEASE`.
```

### Step 4: KRISS KROSS Handoff (if crossing agents)

```
KRISS-KROSS-HANDSHAKE
from_agent=kilocode-glm
to_agent=<destination>
branch=<branch>
scope=<scope>
collision_risk=low|medium|high
fallback_mode=ff|overlay|three_way
graphiti_ref=<trail-ref>
```

## Trigger Phrases

- "sign trail"
- "chit sign"
- "release claim"
- "agent handoff"
- "darkxside witness"
