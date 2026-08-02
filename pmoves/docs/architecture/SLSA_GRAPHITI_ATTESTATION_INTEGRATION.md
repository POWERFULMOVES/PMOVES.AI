# SLSA Level 3 + GRAPHITI PROTOCOL Integration Analysis

GRAPHITI_MARK: `PHI-4482-REVIEW::SLSA-GRAPHITI-INTEGRATION::PMOVES`

> **Purpose:** Architectural analysis connecting GitHub Artifact Attestations (SLSA Level 3)
> with the PMOVES GRAPHITI signing protocol, CHIT cryptographic messaging, CGPS agent cards,
> and agent work attestation into a unified supply chain trust chain.
>
> **Trigger:** PMOVES-P2 Recommendation #3 execution (container resource limits), AGNOTE4482 review.
> **Reference:** https://github.blog/enterprise-software/devsecops/enhance-build-security-and-reach-slsa-level-3-with-github-artifact-attestations/

---

## Executive Summary

PMOVES.AI already operates three distinct signing/attestation layers. Adding SLSA Level 3
via GitHub Artifact Attestations creates a fourth layer, completing a full-stack trust chain
from build provenance through runtime message integrity to agent work attribution.

```
┌─────────────────────────────────────────────────────────────────┐
│                    PMOVES ATTESTATION STACK                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  L4: AGENT SIGNING  ─── GRAPHITI protocol                      │
│      Agent identity + scope + timestamp on all work products     │
│      Pattern: ACK::AGENT-NAME::SCOPE::TIMESTAMP                 │
│      Artifact: GRAPHITI_MARK comments, commit trailers          │
│                                                                 │
│  L3: RUNTIME MESSAGING ──── CHIT protocol                      │
│      Cryptographic signatures on inter-service messages          │
│      CGP geometry packets with Merkle shape attribution          │
│      Artifact: CGP v0.1/v0.2 packets on geometry bus            │
│                                                                 │
│  L2: DEPLOY CONTRACT ────── docker-compose                      │
│      Resource limits, security opts, network isolation           │
│      Artifact: compose YAML with deploy.resources.limits        │
│                                                                 │
│  L1: BUILD PROVENANCE ───── SLSA Level 3 (PROPOSED)            │
│      Cryptographic build attestations via GitHub Actions         │
│      Reusable workflow + actions/attest-build-provenance         │
│      Artifact: signed OCI attestation on GHCR images            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Current State: Three Existing Layers

### L2: Deploy Contract (docker-compose)

**Status:** Implemented (PMOVES-P2 Rec #3)

All 83 services now have `deploy.resources.limits` classified by operational tier:
- Lightweight: 0.5 CPU / 256M (tunnels, proxies, echo services)
- Standard: 1.0 CPU / 512M (workers, agents, gateways)
- Heavy: 2.0 CPU / 2G (LLM inference, RAG)
- GPU: 4.0 CPU / 8G (model serving, whisper, vision)
- Database: 2.0 CPU / 4G (Postgres, Neo4j, Qdrant)

This forms the **resource contract** — each container declares its expected resource envelope.
Future: this contract can be verified at admission time against actual usage.

### L3: Runtime Messaging (CHIT Protocol)

**Status:** 75% implemented (per CHIT_IMPLEMENTATION_AUDIT_2026-02-08)

CHIT (Compressed Hierarchical Information Transfer) provides:
- **Geometry Packets (CGP):** Structured messages encoding content as geometric shapes
- **Shape Attribution:** Merkle-proof-based attribution tracking via `shape-attribution.ts`
- **Five Mathematical Pillars:** Dirichlet distributions, hyperbolic geometry, Merkle proofs,
  zeta spectral filtering, swarm optimization — all implemented in TypeScript
- **NATS Geometry Bus:** Subjects like `geometry.cgp.v1`, `tokenism.attribution.recorded.v1`

Key CHIT env vars already present across services:
- `CHIT_REQUIRE_SIGNATURE` — enforce signing on message exchange
- `CHIT_DECRYPT_ANCHORS` — control geometry packet decryption
- `CHIT_PASSPHRASE` — shared secret for message integrity

### L4: Agent Signing (GRAPHITI Protocol)

**Status:** Active since 2026-02-20

GRAPHITI provides agent-level attestation for all work products:
- **GRAPHITI_MARK:** Canonical identity tag (`PHI-4482-GATEWAY::PMOVES`)
- **Agent ACK:** Signed work claims (`ACK::AGENT-NAME::SCOPE`)
- **Signoff Checklist:** Multi-agent merge gate (AGNOTE4482_SIGNOFF_CHECKLIST.md)
- **Safe Traversal:** Protocol for agent movement across branches/lanes

Current signatories in the ledger:
- `CODEX-GPT5` — docs/prospectus convergence
- `Z890-CLAUDE` — infra/ops primary (runtime verified)
- `4090-CLAUDE` — provider cascade
- `CLAUDE-OPUS` — self-review/docs audit

---

## Proposed: L1 Build Provenance (SLSA Level 3)

### What SLSA Level 3 Requires

Per the GitHub blog on Artifact Attestations:

| SLSA Level | Requirement | PMOVES Status |
|------------|-------------|---------------|
| Level 1 | Build provenance generated | **NEEDED** |
| Level 2 | Hosted build platform | **EXISTS** (self-hosted runners + GH Actions) |
| Level 3 | Non-falsifiable provenance via reusable workflow | **NEEDED** |

### Implementation Plan

#### Step 1: Create Reusable Provenance Workflow

```yaml
# .github/workflows/attest-provenance.yml (reusable)
name: attest-build-provenance

on:
  workflow_call:
    inputs:
      artifact-name:
        required: true
        type: string
      digest:
        required: true
        type: string

permissions:
  contents: read
  id-token: write    # Required for sigstore signing
  attestations: write
  packages: write

jobs:
  attest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/attest-build-provenance@v1
        with:
          subject-name: ${{ inputs.artifact-name }}
          subject-digest: ${{ inputs.digest }}
          push-to-registry: true
```

#### Step 2: Integrate into Existing Build Pipelines

Current build workflows (`build-images.yml`, `integrations-ghcr.yml`,
`self-hosted-builds-hardened.yml`) already:
- Use `step-security/harden-runner@v2`
- Build to GHCR (`ghcr.io/powerfulmoves`)
- Have Docker Buildx setup

Add post-build attestation step:

```yaml
      - name: Generate build attestation
        id: provenance
        uses: actions/attest-build-provenance@v1
        with:
          subject-name: ghcr.io/powerfulmoves/${{ matrix.name }}
          subject-digest: ${{ steps.push.outputs.digest }}
          push-to-registry: true
```

#### Step 3: Verification at Deploy Time

```bash
# CLI verification
gh attestation verify ghcr.io/powerfulmoves/pmoves-agent-zero \
  --repo POWERFULMOVES/PMOVES.AI

# Kubernetes admission (future)
# Policy agent verifies attestation before allowing pod creation
```

---

## Integration: How All Four Layers Connect

### The Attestation Chain

```
BUILD (L1) ──── Image pushed to GHCR with SLSA provenance
   │              Verification: gh attestation verify
   ▼
DEPLOY (L2) ──── Container starts with declared resource limits
   │              Verification: docker compose config / admission webhook
   ▼
RUNTIME (L3) ─── Services exchange CHIT-signed CGP packets
   │              Verification: CHIT_REQUIRE_SIGNATURE + shape Merkle proofs
   ▼
AGENT (L4) ──── Agent signs work with GRAPHITI_MARK
                  Verification: AGNOTE4482 signoff checklist
```

### CGPS Agent Cards as Living Attestation Documents

Agent cards (`.well-known/agent-card.json`, `.well-known/agent.json`) already
define agent identity. With SLSA Level 3, these become **attestation-capable**:

```json
{
  "name": "Agent Zero PMOVES",
  "url": "http://agent-zero:8080",
  "capabilities": [...],
  "attestations": {
    "build_provenance": {
      "subject": "ghcr.io/powerfulmoves/pmoves-agent-zero@sha256:...",
      "verified_by": "gh attestation verify",
      "slsa_level": 3
    },
    "chit_identity": {
      "public_key": "...",
      "geometry_bus_subjects": ["geometry.cgp.v1"]
    },
    "graphiti_signatures": [
      {
        "agent": "AGENT-ZERO",
        "mark": "PHI-4482-GATEWAY::PMOVES",
        "latest_ack": "ACK::AGENT-ZERO::P2-CONTAINER-RESOURCE-LIMITS"
      }
    ]
  }
}
```

### Shape Attribution as Build Artifact Link

The existing `shape-attribution.ts` (621 lines) uses Merkle proofs for content
attribution. This can be extended to also carry **build provenance hashes**:

```
CGP Packet {
  content_hash: sha256(...),
  merkle_proof: [...],
  // NEW: link to build provenance
  build_attestation: {
    image_digest: "sha256:...",
    provenance_digest: "sha256:...",
    builder_identity: "POWERFULMOVES/PMOVES.AI/.github/workflows/build-images.yml"
  }
}
```

This creates an **unbroken chain** from the content inside a CHIT message all the
way back to the specific GitHub Actions run that built the container producing it.

### Agent Signing for Work Done

The GRAPHITI protocol already handles agent work signing. With SLSA integration,
agent ACKs gain an additional attestation dimension:

```
Agent ACK {
  agent: "AGENT-ZERO",
  signature: "ACK::AGENT-ZERO::P2-CONTAINER-RESOURCE-LIMITS",
  timestamp: "2026-04-10T06:58:00-04:00",
  // ENHANCED: link to build provenance of the agent's own container
  running_as: {
    image: "ghcr.io/powerfulmoves/pmoves-agent-zero@sha256:...",
    build_attestation: "slsa://POWERFULMOVES/PMOVES.AI/workflows/build-images.yml@ref1"
  }
}
```

This means every agent action is traceable to:
1. **Which agent** performed it (GRAPHITI identity)
2. **What container** it ran in (image digest)
3. **How that container was built** (SLSA provenance)
4. **What runtime messages** it produced (CHIT signatures)

---

## Implementation Roadmap

### Phase 1: SLSA Level 3 Foundation (Week 1-2)
1. Create `.github/workflows/attest-provenance.yml` reusable workflow
2. Add `actions/attest-build-provenance@v1` to `build-images.yml`
3. Add attestation to `integrations-ghcr.yml` matrix builds
4. Set `permissions: id-token: write, attestations: write` on build workflows
5. Verify with `gh attestation verify` against GHCR images

### Phase 2: Agent Card Attestation Extension (Week 3)
1. Extend A2A agent card schema with `attestations` block
2. Build agent card generator that queries current image digest + provenance
3. Serve enriched agent cards from `/.well-known/agent-card.json`
4. Add agent card attestation to health check endpoints

### Phase 3: CHIT-Build Provenance Bridge (Week 4)
1. Extend CGP schema with optional `build_attestation` field
2. Update `cgp-generator.ts` to embed current image provenance
3. Update `chit_decoder.py` to extract and verify provenance
4. Add NATS subject `geometry.attestation.build.v1` for provenance events

### Phase 4: GRAPHITI-SLSA Agent Signing (Week 5)
1. Extend GRAPHITI ACK schema with `running_as` container identity
2. Build commit-msg hook that auto-injects build provenance into GRAPHITI_MARK
3. Create verification tool: `pmoves tools verify-attestation-chain <service>`
4. Add attestation chain status to `topology_chit_gate.py` checks

---

## Key Integration Points with Existing PMOVES Infrastructure

| Component | Integration | Purpose |
|-----------|-------------|----------|
| `build-images.yml` | Add `actions/attest-build-provenance` | Generate SLSA provenance on push |
| `integrations-ghcr.yml` | Add attestation step to matrix | Cover all integration images |
| `topology_chit_gate.py` | Add attestation verification | Runtime provenance check |
| `shape-attribution.ts` | Extend CGP with build digest | Link content to build |
| Agent card schema | Add `attestations` block | Living attestation document |
| GRAPHITI ACK pattern | Add `running_as` container ID | Agent-to-build traceability |
| AGNOTE4482 signoff | Add attestation verification | Merge gate includes SLSA check |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Self-hosted runners may not support `id-token: write` | Use `ubuntu-latest` for attestation step only |
| CGP schema extension breaks existing consumers | Make `build_attestation` optional field |
| Agent card size bloat from attestation data | Use digest references, not inline certificates |
| Key rotation if GitHub Sigstore instance changes | GitHub manages keys; verification uses `gh` CLI |

---

## Signature

- Agent: `AGENT-ZERO` (Master Developer)
- Signature: `ACK::AGENT-ZERO::SLSA-GRAPHITI-INTEGRATION-ANALYSIS`
- Timestamp: `2026-04-10T07:10:00-04:00`
- Scope: Architectural analysis connecting SLSA L3, CHIT, GRAPHITI, CGPS

<!-- GRAPHITI_MARK: AGENT-ZERO::SLSA-GRAPHITI-INTEGRATION::2026-04-10 -->
