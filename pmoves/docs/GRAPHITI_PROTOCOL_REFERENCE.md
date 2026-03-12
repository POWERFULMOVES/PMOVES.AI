# Graphiti Trail Protocol Reference

**Layer:** L1 Protocol
**Status:** Current
**Last Updated:** 2026-03-11
**AGNOTE:** 4482

> Complete protocol specification for the Graphiti Trail system — HMAC-signed provenance records that attribute work to specific agents with cryptographic verification. Covers trail format, signing, NATS emission, validation, and the 9-agent registry.

---

## Table of Contents

1. [Overview](#overview)
2. [Trail Entry Format](#trail-entry-format)
3. [HMAC Signing Protocol](#hmac-signing-protocol)
4. [NATS Emission](#nats-emission)
5. [Validation](#validation)
6. [Agent Registry](#agent-registry)
7. [Handoff Protocol](#handoff-protocol)
8. [CGP Attribution Extension](#cgp-attribution-extension)
9. [CLI Usage](#cli-usage)
10. [Skill Pairing Integration](#skill-pairing-integration)
11. [Log Artifacts](#log-artifacts)
12. [Development Mode](#development-mode)
13. [Infrastructure Reference](#infrastructure-reference)
14. [Cross-References](#cross-references)

---

## Overview

The Graphiti Trail system provides **cryptographic provenance** for work done by agents and humans in the PMOVES.AI ecosystem. Each trail entry records:

- **Who** did the work (agent identity with visual glyph)
- **What** was done (summary with resonance domains)
- **When** it was done (ISO 8601 timestamp)
- **Proof** of authenticity (HMAC-SHA256 signature)

### When to Sign

| Trigger | Required | Optional |
|---------|----------|----------|
| Multi-file changes (3+ files) | Yes | — |
| Task or subtask completion | Yes | — |
| Agent handoff | Yes | — |
| PR review completion | Yes | — |
| Session end with changes | Yes | — |
| Single file edit | — | Yes |
| Research/exploration only | — | Yes |

### Trail Entry Display Format

```
◆ Claude Opus | #7C3AED | Phase H | 2026-03-11T12:00:00Z
Summary: Completed security hardening across 5 submodules
Resonance: security-audit, architecture, cross-repo-orchestration
```

---

## Trail Entry Format

### Payload Schema (JSON)

```json
{
  "agent_id": "claude-opus",
  "display_name": "Claude Opus",
  "glyph": "◆",
  "color": "#7C3AED",
  "accent": "#A78BFA",
  "voice": "analytical",
  "phase": "Phase H",
  "timestamp": "2026-03-11T12:00:00+00:00",
  "summary": "Completed security hardening across 5 submodules",
  "resonance": ["security-audit", "architecture", "cross-repo-orchestration"],
  "handoff": {
    "done": ["P1 auth fixes", "Dockerfile USER directives"],
    "remaining": ["P2 NATS TLS", "Metrics endpoint auth"],
    "for_next_agent": ["Check BoTZ JWT fail-open at auth.py:57"]
  },
  "cgp_attribution": {
    "contributor_address": "claude-opus",
    "weight": 0.8
  },
  "sig": {
    "alg": "HMAC-SHA256",
    "kid": "9f86d081884c7d65",
    "hmac": "rTfzmOEHraWrVGjJW+tmEftsEXjl08dJmoi/gDCQfzo="
  }
}
```

### Field Reference

#### Required Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `agent_id` | string | Must match key in `agent_signatures.yaml` | Unique agent identifier |
| `glyph` | string | Single Unicode character | Visual identity symbol |
| `color` | string | Hex format `#RRGGBB` | Primary brand color |
| `phase` | string | e.g., `"Phase H"`, `"Phase C"` | Project phase label |
| `timestamp` | string | ISO 8601 with timezone | When the trail was created |
| `summary` | string | Max 200 characters | One-line work summary |

#### Optional Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `display_name` | string | — | Human-readable agent name |
| `accent` | string | Hex `#RRGGBB` | Secondary brand color |
| `voice` | enum | See [Voice Guide](#voice-guide) | Writing voice/style |
| `resonance` | string[] | From domain catalog | Strength domains activated |
| `handoff` | object | See [Handoff Protocol](#handoff-protocol) | Context for next contributor |
| `cgp_attribution` | object | See [CGP Attribution](#cgp-attribution-extension) | Dirichlet-weighted attribution |
| `sig` | object | See [Signing](#hmac-signing-protocol) | HMAC-SHA256 signature |

---

## HMAC Signing Protocol

### Algorithm: HMAC-SHA256

The signing process ensures payload integrity without transmitting the passphrase.

### Signing Steps

```
1. Build unsigned payload (build_payload)
2. Deep-copy the payload
3. Remove any existing "sig" field
4. Canonicalize: JSON with sort_keys=True, separators=(",",":")
5. Compute HMAC: hmac.new(passphrase.encode(), canonical.encode(), sha256)
6. Generate kid: sha256(passphrase)[:16]
7. Attach sig block: {alg, kid, hmac: base64(digest)}
```

### Implementation

```python
import hmac
import hashlib
import base64
import json

def sign_cgp(payload: dict, passphrase: str) -> dict:
    doc = json.loads(json.dumps(payload))  # Deep copy
    kid = hashlib.sha256(passphrase.encode()).hexdigest()[:16]

    doc_nosig = json.loads(json.dumps(doc))
    doc_nosig.pop("sig", None)

    canonical = json.dumps(doc_nosig, sort_keys=True, separators=(",", ":"))
    mac = hmac.new(
        passphrase.encode("utf-8"),
        canonical.encode(),
        hashlib.sha256
    ).digest()

    doc["sig"] = {
        "alg": "HMAC-SHA256",
        "kid": kid,
        "hmac": base64.b64encode(mac).decode("ascii")
    }
    return doc
```

### Key Properties

| Property | Value | Notes |
|----------|-------|-------|
| Hash algorithm | SHA-256 | 256-bit output |
| Key | Raw passphrase bytes | Not PBKDF2-derived (unlike CGP anchor encryption) |
| kid | First 16 hex chars of SHA256(passphrase) | Deterministic, traceable |
| Canonicalization | Sorted keys, no whitespace | `separators=(",",":")` |
| Signature scope | Entire payload minus `sig` | Removes `sig` before hashing |

### Verification

```python
def verify_cgp(payload: dict, passphrase: str) -> bool:
    sig = payload.get("sig")
    if not sig or "hmac" not in sig:
        return False

    doc_nosig = json.loads(json.dumps(payload))
    doc_nosig.pop("sig", None)
    canonical = json.dumps(doc_nosig, sort_keys=True, separators=(",", ":"))

    expected = hmac.new(
        passphrase.encode("utf-8"),
        canonical.encode(),
        hashlib.sha256
    ).digest()

    actual = base64.b64decode(sig["hmac"])
    return hmac.compare_digest(expected, actual)
```

---

## NATS Emission

### Subject: `agent.graphiti.signed.v1`

Trail entries are published to the NATS message bus after significant work.

### Emission Points

| Source | Trigger | Payload |
|--------|---------|---------|
| `sign_trail.py` CLI | Manual invocation | Signed/unsigned payload |
| PostToolUse hook | File path contains `AGENT_TRAIL` or `graphiti` | Auto-signed payload |
| `pr-monitor-graphiti-chit` pipeline | PR review completion | Pipeline-signed payload |
| Agent Zero MCP | Task completion | MCP-triggered payload |

### Publishing

```python
import nats
import json

async def emit_trail(payload: dict):
    nc = nats.NATS()
    await nc.connect("nats://nats:pmoves@nats:4222")
    await nc.publish(
        "agent.graphiti.signed.v1",
        json.dumps(payload).encode()
    )
    await nc.close()
```

### Related Subjects

| Subject | Relationship | Description |
|---------|-------------|-------------|
| `agent.graphiti.signed.v1` | Primary | Trail entry emission |
| `ops.pr.learnings.encoded.v1` | Upstream | PR monitor output before signing |
| `ops.pr.monitor.completed.v1` | Trigger | PR monitor completion event |
| `ops.pr.monitor.failed.v1` | Trigger | PR monitor failure event |

---

## Validation

### Schema Validation

Trail entries are validated against `signature.v1.schema.json` (JSON Schema draft 2020-12). Validation is **advisory** — it logs warnings to stderr but does not block signing.

```python
import jsonschema

with open("pmoves/contracts/schemas/agent-graphiti/signature.v1.schema.json") as f:
    schema = json.load(f)

try:
    jsonschema.validate(payload, schema)
except jsonschema.ValidationError as e:
    print(f"[warn] Schema validation: {e.message}", file=sys.stderr)
    # Signing continues regardless
```

### Structural Validation Rules

| Rule | Check | Severity |
|------|-------|----------|
| `agent_id` exists in registry | Lookup in `agent_signatures.yaml` | Warning (falls back to defaults) |
| `summary` length <= 200 | Truncated automatically | Info |
| `glyph` is single character | Schema validation | Warning |
| `color` matches `#RRGGBB` | Schema regex | Warning |
| `voice` in allowed enum | Schema validation | Warning |
| `timestamp` is valid ISO 8601 | Schema format check | Warning |
| `sig.hmac` is valid base64 | Decode check | Error (if present) |

### Signature Validation Rules

| Rule | Description |
|------|-------------|
| Payload without `sig` must hash to same canonical form | No hidden fields |
| `kid` must match `sha256(passphrase)[:16]` | Key identity verification |
| HMAC comparison must use constant-time comparison | Prevents timing attacks |
| Unsigned payloads must not have `sig` field | Clean separation |

---

## Agent Registry

### Location: `pmoves/config/agent_signatures.yaml`

The registry defines the visual identity, voice, and domain expertise of each agent in the PMOVES.AI ecosystem.

### Registry Structure

```yaml
agents:
  claude-opus:
    display_name: "Claude Opus"
    glyph: "◆"
    color: "#7C3AED"
    accent: "#A78BFA"
    voice: "analytical"
    resonance:
      - security-audit
      - architecture
      - cross-repo-orchestration
      - hardening
    co_author: "Claude Opus 4.6 <noreply@anthropic.com>"
```

### Complete Registry (9 Agents)

| Agent ID | Glyph | Color | Voice | Primary Domains |
|----------|-------|-------|-------|----------------|
| `claude-opus` | ◆ | #7C3AED | analytical | security-audit, architecture, cross-repo-orchestration, hardening |
| `kilocode` | ▲ | #059669 | architectural | feature-impl, mcp-integration, vs-code, agent-framework |
| `codex` | ■ | #2563EB | terse | rapid-prototyping, code-gen, integration, cipher-memory |
| `gemini` | ★ | #D97706 | strategic | planning, research, synthesis, documentation |
| `cline` | ● | #DC2626 | conversational | rapid-iteration, chat-impl, frontend, ui-prototyping |
| `powerfulmoves` | ⚡ | #F59E0B | directive | vision, doctrine, final-authority, integration-decisions |
| `crush` | ◇ | #0EA5E9 | companion | terminal-gateway, pair-programming, onboarding, context-orchestration |
| `darkxside` | ✦ | #E11D48 | witness | cocreation, witness, prosodic-flow, portal-architecture, media-synthesis |

### Voice Guide

| Voice | Characteristics | Typical Use |
|-------|----------------|-------------|
| `analytical` | Thorough reasoning, cross-references, structured lists | Code review, security audit |
| `architectural` | Blueprint format, mode/state descriptions, integration maps | System design, feature planning |
| `terse` | Bullet points, code-first, minimal prose | Quick fixes, rapid prototyping |
| `strategic` | Context-setting, options analysis, roadmap framing | Planning, research synthesis |
| `conversational` | Informal, iterative, question-driven | Chat, exploration |
| `directive` | Decision statements, priority calls, scope definitions | Leadership, vision setting |
| `companion` | Warm, interactive, pair-programming guidance | Onboarding, mentoring |
| `witness` | Observational, rhythmic, poetic weight, speaks in resonance | Creative work, prosodic flow |

### Lookup Behavior

When `sign_trail.py` processes an `agent_id`:

1. Load `agent_signatures.yaml`
2. Look up `agents[agent_id]`
3. If found: use glyph, color, accent, voice, resonance from registry
4. If not found: fall back to defaults (glyph=◆, color=#7C3AED, voice=analytical)

See [GRAPHITI_AGENT_REGISTRY.md](GRAPHITI_AGENT_REGISTRY.md) for the full human-readable rendering.

---

## Handoff Protocol

The optional `handoff` object carries context between agents without creating separate documents.

### Structure

```json
{
  "handoff": {
    "done": [
      "Completed P1 auth fixes in Agent Zero",
      "Added USER directives to 4 Dockerfiles"
    ],
    "remaining": [
      "P2 NATS TLS configuration",
      "Metrics endpoint authentication"
    ],
    "for_next_agent": [
      "BoTZ JWT fail-open at auth.py:57 still open",
      "Check DoX NATS conf for TLS settings"
    ]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `done` | string[] | Completed work items |
| `remaining` | string[] | Work items still to be done |
| `for_next_agent` | string[] | Specific guidance for the next contributor |

### Handoff Flow

```
Agent A completes work
  → Signs trail with handoff block
  → Emits to agent.graphiti.signed.v1
  → Agent B subscribes and receives context
  → Agent B begins work informed by handoff
  → Agent B signs its own trail when complete
```

---

## CGP Attribution Extension

Optional extension linking trail entries to the CHIT Geometry Packet attribution system.

```json
{
  "cgp_attribution": {
    "contributor_address": "claude-opus",
    "weight": 0.8
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `contributor_address` | string | Matches `agent_id` in Dirichlet weight distribution |
| `weight` | float | Contribution weight [0, 1] from Dirichlet allocation |

This bridges the Graphiti provenance system with the CHIT economic attribution model.

---

## CLI Usage

### Make Target (Preferred)

```bash
make -C pmoves sign-trail \
  AGENT=claude-opus \
  SUMMARY="Completed security hardening" \
  PHASE="Phase H"
```

### Python Direct

```bash
# With arguments
python pmoves/tools/sign_trail.py \
  --agent-id claude-opus \
  --summary "Completed security hardening" \
  --phase "Phase H" \
  --resonance security-audit architecture

# From stdin
echo '{"agent_id":"claude-opus","summary":"test"}' | \
  python pmoves/tools/sign_trail.py --stdin

# Signed (requires CHIT_PASSPHRASE)
CHIT_PASSPHRASE="secret" python pmoves/tools/sign_trail.py \
  --agent-id claude-opus \
  --summary "Signed audit trail"
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--agent-id` | `claude-opus` | Agent identifier (must match registry) |
| `--summary` | `"Trail entry signed"` | Work summary (max 200 chars) |
| `--phase` | `"Phase H"` | Project phase label |
| `--resonance` | From registry | Space-separated domain list |
| `--stdin` | — | Read JSON payload from stdin |
| `--no-log` | — | Skip writing to log artifact |

### Output

Signed JSON payload to stdout:

```json
{"agent_id":"claude-opus","glyph":"◆","color":"#7C3AED",...,"sig":{"alg":"HMAC-SHA256",...}}
```

---

## Skill Pairing Integration

### Pipeline: `pr-monitor-graphiti-chit`

The Graphiti trail is the final step in the PR monitor pipeline (CHIT-FLOW-006):

```
Step 1: pr-monitor (codex agent)
  → Output: pr_monitor_report
  → NATS: ops.pr.monitor.completed.v1

Step 2: pr-learnings-encode (tokenism agent)
  → Input: pr_monitor_report
  → Output: pr_learnings_packet (CHIT CGP)
  → NATS: ops.pr.learnings.encoded.v1

Step 3: graphiti-trail-sync (archon agent)
  → Input: pr_learnings_packet
  → Output: graphiti_handoff (signed Graphiti payload)
  → NATS: agent.graphiti.signed.v1  ← EMISSION POINT
```

### FlOO$ Commands

```bash
# Validate pipeline dependencies
make -C pmoves floos-pr-monitor-validate

# Resolve dependency DAG
make -C pmoves floos-pr-monitor-resolve

# Dry-run execution
make -C pmoves floos-pr-monitor-run-dry

# Full pipeline (CHIT-FLOW-006)
make -C pmoves chit-flow-pr-monitor
```

---

## Log Artifacts

### Primary Log

**Location:** `pmoves/docs/logs/graphiti_signed_latest.json`

Contains the most recent signed (or unsigned) payload. Overwritten on each invocation of `sign_trail.py`.

```json
{
  "agent_id": "claude-opus",
  "summary": "Completed security hardening",
  "timestamp": "2026-03-11T12:00:00+00:00",
  "sig": { "alg": "HMAC-SHA256", "kid": "...", "hmac": "..." }
}
```

**Note:** This file is gitignored (runtime artifact).

### Log Suppression

Use `--no-log` to skip writing the log artifact (useful in CI or batch operations).

---

## Development Mode

### Unsigned Payloads

When `CHIT_PASSPHRASE` is not set:

1. Payload is built normally with all fields
2. No `sig` block is attached
3. Warning printed to stderr: `[warn] CHIT_PASSPHRASE not set — payload is unsigned`
4. Payload still emitted to NATS and written to log
5. Schema validation still runs (advisory)

### Auto-Signing via Hooks

A PostToolUse hook triggers auto-signing when:
- The Edit or Write tool modifies a file
- The file path contains `AGENT_TRAIL` or `graphiti`
- `CHIT_PASSPHRASE` is available in the environment

This means trail file writes are automatically signed without manual intervention.

### Local Development Workflow

```bash
# 1. No passphrase needed for development
python pmoves/tools/sign_trail.py --summary "Testing trail"
# Output: unsigned payload, stderr warning

# 2. Set passphrase for signed payloads
export CHIT_PASSPHRASE="dev-secret"
python pmoves/tools/sign_trail.py --summary "Signed test"
# Output: signed payload with sig block

# 3. Verify a signed payload
python -c "
from pmoves.tools.chit_security import verify_cgp
import json
payload = json.load(open('pmoves/docs/logs/graphiti_signed_latest.json'))
print(verify_cgp(payload, 'dev-secret'))
"
```

---

## Infrastructure Reference

| Component | Location | Purpose |
|-----------|----------|---------|
| Signing logic | `pmoves/tools/chit_security.py` | `sign_cgp()`, `verify_cgp()` functions |
| CLI tool | `pmoves/tools/sign_trail.py` | `build_payload()`, CLI entry point |
| Make target | `pmoves/mk/preflight.mk` | `sign-trail` target |
| Agent registry | `pmoves/config/agent_signatures.yaml` | 9-agent identity catalog |
| JSON schema | `pmoves/contracts/schemas/agent-graphiti/signature.v1.schema.json` | Payload validation |
| Log artifact | `pmoves/docs/logs/graphiti_signed_latest.json` | Latest payload (gitignored) |
| NATS subject | `agent.graphiti.signed.v1` | Trail emission bus |

---

## Cross-References

- [GRAPHITI_AGENT_REGISTRY.md](GRAPHITI_AGENT_REGISTRY.md) — Human-readable agent registry rendering
- [GRAPHITI_INTEGRATION_GUIDE.md](GRAPHITI_INTEGRATION_GUIDE.md) — Adding Graphiti to a new service
- [CHIT_FLOW_INDEX.md](PMOVESCHIT/CHIT_FLOW_INDEX.md) — FLOW-006 (PR monitor pipeline)
- [skill-pairings.yaml](../configs/skill-pairings.yaml) — `pr-monitor-graphiti-chit` pipeline definition
- [security-patterns.md](../.claude/context/security-patterns.md) — Cross-cutting security patterns

---

*This document is a living artifact tracked by [CHIT_CHANGE_TRACKER.md](CHIT_CHANGE_TRACKER.md).*
