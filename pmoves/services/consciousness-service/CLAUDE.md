# consciousness-service — Subsystem Context

> Subsystem-specific CLAUDE.md. Load on demand when working inside `pmoves/services/consciousness-service/`. README and `pmoves/docs/TAC/TAC_CONSCIOUSNESS.md` cover the architecture; this doc captures the developer-facing rules for Claude.

## Why this service is high-stakes

This is the **CHIT-Full-tier service that bridges the symbolic (Tokenism agent interactions) and the geometric (Neo4j-backed CGP graph)**. A bug here can:
- Corrupt the swarm topology graph
- Break CHIT signature verification across downstream services
- Silently change simulation results in Tokenism

Treat every code change here as audit-impacting. Pair every PR with a TAC tree review (`/tac:review consciousness-service` once that TAC is wired into the runner) AND an update to `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md` if the CHIT tier changes.

## CGP schema versioning rules

- The **payload schema** uses semantic versioning `chit.cgp.v{major}.{minor}`. Major bumps are breaking; minor are backwards-compatible.
- The **NATS transport** uses `geometry.cgp.v{N}` — integer-only. A transport bump happens ONLY when the message envelope (not the payload) changes incompatibly.
- **Never** invent a new transport version casually. Coordinate with Tokenism + Hi-RAG consumers via the `nats-subject-auditor` subagent (`.claude/agents/nats-subject-auditor.md`).

## Three-Body governance

This service is named in AGNOTE4482's Three-Body model as a Memory-Body anchor (because it produces signed topology). When making changes:
- **Delivery**: implementer.
- **Control**: reviewer must verify CHIT signature trail emission still works (`chit_signing.py`-equivalent code path).
- **Memory**: file a CLAIM/RELEASE entry in `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` for non-trivial changes.

## Common tasks

- **Add a new geometry-emit subject**: ensure subject is registered in `.claude/context/geometry-nats-subjects.md`; run `nats-subject-auditor` subagent on the diff.
- **Change CGP payload schema**: bump `chit.cgp.v{major}.{minor}` per rules above; update Tokenism + Hi-RAG consumers in the same PR (or open paired PRs).
- **Debug topology drift**: query Neo4j directly via `/db:query`; verify CGP packets via `/chit:decode`.
- **Verify CHIT signing**: `/chit:sign-trail` slash command on a known-good payload; confirm round-trip.

## CHIT integration paths

This service is one of the 5 "Full" CHIT-integrated services. Code paths that produce CGP must:
1. Sign each packet via `chit_signing.py` (or equivalent in this service's tree).
2. Publish to `geometry.cgp.v1` with the signed envelope.
3. Persist the signature alongside the graph node in Neo4j.

When refactoring, NEVER skip step 1. The `chit-pr-audit-agent` subagent (`.claude/agents/chit-pr-audit-agent.md`) is wired to block PRs that touch this service without preserving CHIT signature emission.

## Cross-references

- TAC tree: `pmoves/docs/TAC/TAC_CONSCIOUSNESS.md` (canonical).
- Tokenism Simulator pair: `pmoves/services/tokenism-simulator/`.
- Hi-RAG (CGP graph consumer): `pmoves/services/hi-rag-gateway-v2/`.
- CHIT audit: `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md`.
- Subagent: `.claude/agents/chit-compliance-reviewer.md` for compliance review.
