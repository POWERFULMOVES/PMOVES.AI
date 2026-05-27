# CHIT Implementation Matrix

Status: 2026-05-22 gap-closure checkpoint

This matrix replaces broad "five pillars complete" language with the actual
implementation state.

| Area | State | Notes |
| --- | --- | --- |
| Dirichlet attribution | Working | Used in ToKenism CHIT attribution and CGP generation. |
| Merkle attribution proofs | Working | ToKenism now uses configured SHA-256 or keccak256 hashing and order-preserving proof verification. |
| CGP signature/encryption | Working | Python geometry decoder delegates to canonical `pmoves.tools.chit_security`. |
| Poincare disk geometry | Partial | Deterministic points exist for CGP records; broader hyperbolic semantics still need service coverage. |
| Swarm fitness tracking | Working baseline | `swarm.meta.v1` tracks bounded fitness and population metadata; it is not proof of optimization by itself. |
| EvoSwarm operators | Implemented for persona params | Deterministic hybrid PSO/evolution now replaces the temperature-nudge stub for persona runtime parameters. |
| Model fitness tracking | Implemented baseline | `model.fitness.recorded.v1` captures signed normalized scorecards from TensorZero plus optional Pinokio/Unsloth metrics. |
| Zeta filtering | Heuristic | Zeta zero weighting remains heuristic until the method design gate in `docs/architecture/zeta-method-design.md` is accepted. |
| Agent trails | Working baseline | Trusted model/evolution writes require registry, signature, and active signing-card identity. |
| ToKenism economics | Planned | NATS to FireFly to contract flow remains a separate workstream, not a CHIT primitive. |
| Fleet hardening | Partial | 5090 GPU/Docker validation exists; TensorZero health, env interpolation, and Linux SSH trust still need closeout. |

Do not describe CHIT as having complete hyperbolic, zeta, or swarm-optimization
math until the partial/planned rows above move to working with tests.
