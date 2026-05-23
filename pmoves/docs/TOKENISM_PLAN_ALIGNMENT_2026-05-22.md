# Tokenism Plan Alignment - 2026-05-22

**Scope:** PMOVES.AI Tokenism / ToKenism plan-doc review after CHIT hardening and TensorZero 5090 bring-up.

## Current Implementation Truth

Working:
- ToKenism TypeScript CHIT core has real SHA-256 / keccak256 Merkle hashing, order-preserving proof verification, deterministic CGP generation, and schema-validated publisher methods.
- Tokenism settlement has typed requested/recorded/failed NATS contracts, a deterministic planner, and a Firefly dry-run executor that creates transaction drafts without external writes.
- Python CHIT crypto is consolidated through `pmoves.tools.chit_security` compatibility wrappers.
- TensorZero gateway is healthy on the 5090 node after fixing duplicate model tables in the mounted checkout.
- PMOVES model-fitness and EvoSwarm workstreams now have signed scorecard recording and deterministic seeded optimizer operators in the parent repo.

Bounded:
- ToKenism `SwarmAttribution` tracks fitness and population metadata only.
- Zeta filtering is heuristic until a method-design doc is reviewed.
- Hyperbolic encoding is an embedding support layer, not a completed proof-backed economic fairness pillar.

Not done:
- Live production token settlement execution through Firefly and blockchain transactions.
- Hardhat contract harness expansion and deployment manifest validation.
- Trusted optimizer publishing from PMOVES-AGENT-ZERO-CODEX/HERMES/Claw in live runner topology.
- Full stale-doc cleanup outside the Tokenism/CHIT references touched in this pass.

## References Updated In This Pass

| File | Alignment change |
|------|------------------|
| `pmoves/docs/TOKENISM_ECONOMIC_MODEL.md` | Added implementation reality check; replaced overclaims around fairness, evolution, and production token distribution. |
| `pmoves/docs/TOKENISM_DEVELOPER_GUIDE.md` | Fixed CHIT API examples, publisher behavior, zeta wording, and swarm scope. |
| `pmoves/docs/TAC/TAC_TOKENISM.md` | Replaced obsolete module list and marked hyperbolic/zeta/swarm/contract settlement accurately. |
| `pmoves/docs/geometry-bus/services/tokenism-simulator.md` | Corrected Flask endpoints, ports, NATS subjects, and removed fake mutation/crossover claims. |
| `PMOVES-ToKenism-Multi/IMPLEMENTATION_STATUS.md` | Added scope reality check and updated schema/test/status claims. |
| `PMOVES-ToKenism-Multi/PHASE4_*.md` and `INTEGRATED_EXECUTION_PLAN.md` | Clarified that Firefly modules are complete and settlement now has a typed plan-only interface, while live execution remains pending. |
| `PMOVES-ToKenism-Multi/integrations/contracts/SETTLEMENT_FLOW.md` | Defines the signed settlement event flow, idempotency contract, Firefly dry-run path, and live-execution gates. |

## Recommended Next Atomic Workstreams

1. **Tokenism live settlement gate:** wire dry-run results to operator approval, then enable Firefly live mode with executor identity and signed recorded/failed NATS publishing.
2. **Contract harness:** install/verify Hardhat locally, expand GroVault/GroupPurchase/governance tests, and generate deployment/ABI manifests for consumers.
3. **Trusted optimizer bridge:** require PMOVES-AGENT-ZERO-CODEX, HERMES, and Claw signing identities before accepting optimizer output as trusted.
4. **Model-fitness integration:** connect HF candidate discovery, TensorZero telemetry, and Pinokio/Unsloth eval results into persisted `model.fitness.recorded.v1` scorecards.
5. **Zeta method design:** write and review a method document before replacing the heuristic filter with stronger math claims.
