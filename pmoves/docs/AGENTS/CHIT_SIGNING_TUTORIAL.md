# CHIT Signing Tutorial

**Created:** 2026-07-11
**Audience:** PMOVES agents and developers
**Purpose:** Quickstart guide for CHIT signing patterns and workflows

---

## What is CHIT?

CHIT (Compressed Hierarchical Information Transfer) is PMOVES' cryptographic signing system for agent coordination and provenance. It provides:

- **Signature trails**: Attributable agent actions across PMOVES lanes
- **Provenance**: "Who signed what and when" for all production changes
- **Coordination**: Cross-agent handoffs via encrypted payloads
- **Self-stabilization**: Closed-loop correction through trail verification

**Architecture:** CHIT is Layer 2 (Information) in the PMOVES MOF Architecture — the "adsorbed molecule encoding" layer.

---

## Quickstart: 5-Minute Guide

### 1. Set Your Passphrase

```bash
# Required for signed entries (export in your current shell only)
export CHIT_PASSPHRASE="your-secret-passphrase"
```

Do **not** persist the passphrase to `~/.bashrc` or any file. If it is unset,
`sign-trail` still records the entry **unsigned** — repo policy is "signing is
optional locally"; production passphrases are operator-held (voice-activated),
never stored on disk.

### 2. Sign a Trail Entry

After completing work (code changes, documentation, infrastructure):

```bash
make -C pmoves sign-trail \
  SUMMARY="Fixed CHIT verification in Consciousness service" \
  AGENT="B850-CLAUDE" \
  PHASE="P0 CHIT Completion"
```

The target accepts `AGENT`, `SUMMARY`, `PHASE`, and `ARGS` (extra flags passed
through to `pmoves/tools/sign_trail.py`, e.g. `ARGS='--alter ... --resonance ...'`).
Branch/PR context belongs in your register entry (see Patterns below), not in
make variables — unknown variables are silently ignored.

This:
1. Creates a CHIT payload with your metadata
2. Signs it with your passphrase (or records it unsigned when none is set)
3. Writes the signed payload to `pmoves/docs/logs/graphiti_signed_latest.json`
4. Emits to NATS `chit.signed.v1` (when wired)

Note: `sign-trail` does **not** append to `AGNOTE4482PHI.t1.md` — the Active
Claim Register entry is written separately (manually or via the
`pmoves-chit-sign` skill), referencing the signature.

### 3. Sign Before Merging

Always sign before creating a PR or merging to main:

```bash
# After committing changes
make -C pmoves sign-trail \
  SUMMARY="Completed CHIT signing for Evo Controller - ready for review" \
  AGENT="B850-CLAUDE" \
  PHASE="P0 CHIT Completion"
```

### 4. Verify a CGP Packet

To validate a CHIT Geometry Packet (e.g. a handoff artifact):

```bash
python -m pmoves.tools.chit_security_validator path/to/packet.cgp.json --strict
```

Programmatic signature verification lives in `pmoves.tools.chit_security`
(`verify_cgp(cgp, passphrase)`).

---

## Common Patterns

### Pattern 1: Agent Claim Entry

When claiming a lane in AGNOTE4482PHI.t1.md:

```markdown
- `2026-07-11T22:00:00Z` CLAIM `B850-CLAUDE` scope: P0 CHIT Completion - Consciousness/Evo/A2UI signing
  branch: feat/p0-chit-completion
  pr_numbers: []
  risks: None identified
  next_actions: Implement CHIT signing for Consciousness service
```

### Pattern 2: Agent Release Entry

When releasing a lane after completion:

```markdown
- `2026-07-11T23:30:00Z` RELEASE `B850-CLAUDE` scope: P0 CHIT Completion complete
  branch: feat/p0-chit-completion
  pr_numbers: [#2073]
  risks: None
  next_actions: Move to P0 Evaluation Gates
  agent_signature: ACK::B850-CLAUDE::P0-CHIT-COMPLETION
```

### Pattern 3: Handoff with CHIT Payload

For cross-agent handoffs (Three-Body pattern):

```bash
# 1. Export CHIT with no cleartext (secure mode)
make -C pmoves chit-export CHIT_NO_CLEARTEXT=1

# 2. Reference artifact path in handoff note
# In AGNOTE4482PHI.t1.md:
chit_artifact_path: ~/.config/pmoves/chit/env.cgp.json
agent_signature: ACK::B850-CLAUDE::HANDOFF-TO-Z890
```

### Pattern 4: Village Rule Compliance

No agent operates alone in production validation:

1. **Delivery Body** (execution): Implements changes
2. **Control Body** (review): Independent verification
3. **Memory Body** (security): CHIT-safe coordination

All three bodies sign before merge readiness.

---

## Workflow Examples

### Example 1: Simple Bug Fix

```bash
# 1. Fix the bug
vim services/consciousness/server.py
git add services/consciousness/server.py
git commit -m "fix(consciousness): add CHIT signing verification"

# 2. Sign trail
make -C pmoves sign-trail \
  SUMMARY="Added CHIT verification to Consciousness health endpoint" \
  AGENT="B850-CLAUDE"

# 3. Create PR
gh pr create --title "fix(consciousness): CHIT verification" \
  --body "Fixes CHIT signing gap. Signed per Village Rule."
```

### Example 2: Feature Implementation

```bash
# 1. Implement feature (multiple commits)
git commit -m "feat(evo): add CHIT signing to Evo Controller"
git commit -m "test(evo): add CHIT verification tests"

# 2. Run tests
make -C pmoves test

# 3. Sign trail with full scope
make -C pmoves sign-trail \
  SUMMARY="Evo Controller CHIT signing complete - implementation, tests, docs" \
  AGENT="B850-CLAUDE" \
  PHASE="P0 CHIT Completion"

# 4. Create draft PR for review
gh pr create --draft --title "feat(p0): CHIT Completion - Consciousness/Evo"
```

### Example 3: Infrastructure Change

```bash
# 1. Update docker-compose or infrastructure
vim docker-compose.yml
git commit -m "infra(compose): add CHIT verification to gateway"

# 2. Test locally
make -C pmoves up

# 3. Sign with infrastructure scope
make -C pmoves sign-trail \
  SUMMARY="Added CHIT verification to Gateway service compose config" \
  AGENT="B850-CLAUDE" \
  PHASE="infra"
```

---

## Troubleshooting

### "Passphrase not set"

```bash
export CHIT_PASSPHRASE="your-passphrase"
# Or just run without it — entries are recorded unsigned in local dev
# (repo policy: "signing is optional locally"; required in production)
make -C pmoves sign-trail SUMMARY="..." AGENT="..."
```

### "Signature verification failed"

Possible causes:
1. Wrong passphrase used
2. Payload was tampered with
3. Clock skew between systems

```bash
# Validate the CGP packet carrying the signature
python -m pmoves.tools.chit_security_validator path/to/packet.cgp.json --strict

# Re-sign with correct passphrase
export CHIT_PASSPHRASE="correct-passphrase"
make -C pmoves sign-trail SUMMARY="..." AGENT="..."
```

### "Cannot write to AGNOTE4482PHI.t1.md"

File is locked by another agent:
1. Check Active Claim Register in AGNOTE4482PHI.t1.md
2. Contact the claiming agent for handoff
3. Use Village Rule — don't bypass active claims

### "NATS emit failed" (when wired)

NATS connection issue:
```bash
# Check NATS health (monitoring port 8222; 4222 is the client protocol port)
curl -s http://localhost:8222/varz | jq '.server_id'

# Verify credentials
echo $NATS_URL  # Should be nats://user:pass@host:port
```

---

## Tools Reference

### Make Targets

| Target | Purpose |
|--------|---------|
| `make -C pmoves sign-trail` | Sign a trail entry |
| `python -m pmoves.tools.chit_security_validator <cgp.json> --strict` | Validate/verify a CGP packet |
| `make -C pmoves chit-export` | Export secrets as CGP |
| `make -C pmoves chit-manifest-sync` | Sync v1 manifest from v2 |
| `make -C pmoves secrets-funnel` | Run full secrets pipeline |

### Python Tools

| Tool | Purpose |
|------|---------|
| `pmoves.tools.chit_encode_secrets` | Encode env secrets to CGP |
| `pmoves.tools.chit_decode_secrets` | Decode CGP to env secrets |
| `pmoves.tools.chit_security` | Core CHIT crypto operations |
| `pmoves.tools.chit_security_validator` | Validate CGP packets |
| `pmoves.tools.sign_trail` | Sign trail entries |

### Skills

| Skill | Purpose |
|-------|---------|
| `/chit:encode` | Encode CHIT packets interactively |
| `/chit:decode` | Decode CHIT packets interactively |
| `/chit:bpm` | Encode BPM prosody to CHIT |
| `pmoves-chit-sign` | Full sign-trail workflow |

---

## Best Practices

### DO ✓

1. **Always sign before PR** — provenance first, then review
2. **Sign with specific scope** — what did you actually touch?
3. **Include PR numbers** — links signature to code changes
4. **Document risks** — what could go wrong with this change?
5. **Use Village Rule** — get peer review before production

### DON'T ✗

1. **Don't merge unsigned** — all production changes must be signed
2. **Don't sign for others** — each agent signs their own work
3. **Don't skip verification** — check signatures before trusting
4. **Don't expose secrets** — use CHIT export with no cleartext
5. **Don't bypass active claims** — follow collision-avoidance protocol

---

## Architecture Context

### Where CHIT Fits

```
┌─────────────────────────────────────────────────────────┐
│  L1 Structure: Agent Zero + Neo4j                     │
├─────────────────────────────────────────────────────────┤
│  L2 Information: CHIT (Dirichlet, Poincaré, Merkle)    │ ← YOU ARE HERE
├─────────────────────────────────────────────────────────┤
│  L3 Transport: GEOMETRY BUS (NATS JetStream)           │
├─────────────────────────────────────────────────────────┤
│  L4 Optimization: EVO SWARM                             │
├─────────────────────────────────────────────────────────┤
│  L5 Economics: ToKenism                                 │
└─────────────────────────────────────────────────────────┘
```

### CHIT in the Three-Body Pattern

- **Delivery Body**: Signs execution commits
- **Control Body**: Signs governance decisions
- **Memory Body**: Manages CHIT-safe coordination

### CHIT in the MOF Architecture

CHIT is the "self-stabilizing equilibrium" — closed-loop correction through:
1. **Dirichlet attribution** — who contributed what
2. **Poincaré conjecture** — topological integrity
3. **Merkle trees** — hash-based verification
4. **Riemann zeta** — distribution validation

---

## Further Reading

- [CHIT Tools Catalog](../CHIT_TOOLS_CATALOG.md) — Full tools reference
- [PMOVESCHIT/README.md](../PMOVESCHIT/README.md) — Protocol documentation
- [AGNOTE4482.md](AGNOTE4482.md) — Orchestration patterns
- [AGNOTE4482PHI.t1.md](AGNOTE4482PHI.t1.md) — Active Claim Register
- [PMOVES_MOF_ARCHITECTURE.md](../architecture/PMOVES_MOF_ARCHITECTURE.md) — MOF context
- [BOOTSTRAP.md](../../../.claude/BOOTSTRAP.md) — Known Roads

---

## Quick Reference Card

```bash
# Sign a trail entry
make -C pmoves sign-trail SUMMARY="..." AGENT="..." PHASE="..."

# Export secrets securely
make -C pmoves chit-export CHIT_NO_CLEARTEXT=1

# Validate a CGP packet (signature check included)
python -m pmoves.tools.chit_security_validator packet.cgp.json --strict

# Decode CHIT packet
python -m pmoves.tools.chit_decode_secrets --cgp packet.json

# Encode CHIT packet
python -m pmoves.tools.chit_encode_secrets --env-file env.shared
```

---

**Version:** 1.0.0
**Last Updated:** 2026-07-11
**Maintained By:** PMOVES Memory Body
