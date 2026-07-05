# Tokenism Production Activation Pack - 2026-05-27

## Scope

This is the starter pack for moving Tokenism settlement from guarded dry-run into production readiness. It does not enable live settlement by itself. Live execution remains blocked until every required artifact below is present, signed, reviewed, and linked from the relevant deployment manifest.

## Current State

- CHIT and Tokenism hardening fixes are merged through PMOVES.AI PR #1633.
- The transcribe LFS cleanup gitlink is merged through PR #1638.
- Settlement executors support dry-run operation and live gates.
- Firefly and contract live execution require signed executor identity, matching operator approval, signed deployment attestation, and manifest-backed environment references.
- The activation artifact is now represented by `tokenism.activation.pack.v1` and validated by `PMOVES-ToKenism-Multi/integrations/contracts/tokenism-activation-pack.ts`; the schema is mirrored at `pmoves/contracts/schemas/tokenism/activation.pack.v1.schema.json`.

## Required Artifacts

| Artifact | Required | Notes |
|----------|----------|-------|
| `deployment_manifest_id` | Yes | Immutable manifest id for this activation wave |
| `chain_id` | Yes | Production or staging network id; no placeholder values |
| `contract_addresses` | Yes | Deployed contract addresses keyed by contract role |
| `rpc_endpoint_ref` | Yes | Reference to secret-managed RPC endpoint, not the raw URL |
| `wallet_custody_ref` | Yes | Reference to custody policy or signer storage, not the raw key |
| `firefly_endpoint_ref` | Yes | Reference to FireFly environment binding |
| `operator_approval_id` | Yes | Signed operator approval matching executor scope |
| `deployment_attestation_sig` | Yes | CHIT-verifiable attestation over manifest contents |
| `executor_agent_id` | Yes | Must resolve to a trusted signing identity |
| `executor_signature` | Yes | Signature over the live settlement request |
| dry-run evidence | Yes | Firefly and contract dry-runs must pass before live mode |
| rollback plan | Yes | Includes disable switch, affected subjects, and incident contact |

## Activation Sequence

1. Produce a staging deployment manifest with real contract and endpoint references.
2. Run Firefly and contract settlement dry-runs against the staging manifest.
3. Record dry-run results as signed settlement evidence.
4. Review chain, wallet, FireFly, and operator approval references.
5. Sign the deployment attestation.
6. Enable live executor mode only for the approved lane and manifest id.
7. Publish first live result as `tokenism.settlement.recorded.v1` or `tokenism.settlement.failed.v1`.
8. Verify the signed result, trail entry, and downstream registry persistence.

## Validation Gates

- `make -C pmoves submodule-integrity` passes before any gitlink change.
- ToKenism settlement tests pass before executor promotion.
- `tokenism.activation.pack.v1` validates against the contract schema and rejects raw RPC URLs, raw wallet private keys, placeholder refs, missing dry-run evidence, mismatched deployment manifest ids, and untrusted executor ids.
- Dry-run Firefly and contract outputs match schema and signing policy.
- Live executor rejects missing approval, mismatched approval, missing deployment attestation, and unsigned executor identity.
- Operator can disable live mode without redeploying code.

## Open Items

- Choose the first activation network and `chain_id`.
- Bind FireFly endpoint references in the target environment.
- Confirm wallet custody policy and signer storage.
- Confirm which agent identity owns first live settlement execution.
- Decide whether the first live pass is staging-only or production-low-value.
