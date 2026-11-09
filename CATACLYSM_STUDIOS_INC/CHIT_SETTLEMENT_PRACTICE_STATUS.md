# CHIT as Settlement Layer — Crypto Practice Status

> **Status: 2026-10-10.** Sources: `research/analyses/2026-10-05_TOKENISM_CHIT_VERIFICATION_SETTLEMENT_REVIEW.md` + `research/analyses/2026-10-10_CATACLYSM_EVIDENCE_CITATION_REFRESH_AUDIT.md`. Labels are strict: **MEASURED** = code artifact or live probe · **GATED** = blocked on counsel/sign-off · **DESIGNED** = spec only. Simulation outputs are never presented as settlement results (Gap G5).

The L1/L2 tokenized-coop design (Food-USD / GroToken, pooled mesh economics) is no longer paper-only: the attribution math exists as a **measured code artifact**, and the path to live settlement is **defined and gated**, not vague.

## Two-layer thesis

- **CHIT = verification layer** (provenance & authority): every write is wrapped in a signed CGP attestation. MEASURED: canonical sign/verify in `pmoves/tools/chit_security.py`; grep-verified call site in Hi-RAG v2 (`routes/geometry.py:154`, per `research/chit_integration_verification.md`).
- **ToKenism = settlement layer** (contribution → attribution → reward): the weekly GroToken pool splits by measured attribution weight; the A/B counterfactual simulator (Gini, PovertyRate, LocalEconomyStrength, CommunityResilience) stays the policy sandbox.

```
contribution event → CHIT-signed attestation (HMAC receipt)
                   → DirichletWeights.addContribution (α update, decayed)
                   → weekly getExpectedAttribution() → GroToken pool split (settlement)
                   → PMOVES-Wealth ledger (Firefly double-entry; residents read, treasurer writes)
                   → sign-trail entry (audit close-out)
```

## The measured artifact: `integrations/contracts/chit/dirichlet-weights.ts`

- `addContribution(addr, amount, category, week)` raises α pseudo-counts (`alpha = smoothingAlpha + amount × concentrationK`) — MEASURED (code read 2026-10-05)
- `getExpectedAttribution()` returns normalized weights, Σ = 1 — MEASURED
- Defaults: `smoothingAlpha 0.1`, `concentrationK 1.0`, `decayHalfLife 12` (cited `pmoves/docs/pilots/fordham-hill/03-tokenism-pooled-mesh-sim.md:134-152`)

## Governance firewall (bylaws Clause L)

Contribution tokens MUST NOT translate into vote weight — **settlement ≠ vote power**; one-unit-one-vote stays supreme (`pmoves/docs/pilots/fordham-hill/04-governance-bylaws-scaffold.md` Clause L, enforced in settlement review §2).

## Gap register G1–G5 (live re-verification 2026-10-05)

| Gap | Status 2026-10-05 | Evidence |
|---|---|---|
| G1 Tokenism Simulator verify gate | **CLOSED** | `services/chit_encoder.py:20` imports canonical sign/verify; real call site `services/simulation_engine.py:137` (`self.chit.sign_cgp_packet(cgp)`) |
| G2 Gateway duplicate inline crypto | **CLOSED** | `gateway/api/chit.py:21` delegates to canonical `verify_cgp` |
| G3 CHIT signatures disabled by default | OPEN (GATED) | Flip `CHIT_REQUIRE_SIGNATURE=true` at docked-mode transition |
| G4 Run manifests / burn-lists unsigned | OPEN | PR #3204 review Gaps A+B: CGP packets + HMAC with real call sites in `scrub_chats.py` |
| G5 Sim outputs ≠ settlement results | STANDING RULE | Keep PROJECTION/ARITHMETIC labels; settlement only on the production ledger |

Spread added 2026-10-05: verify/signed coverage now also in a2ui-nats-bridge (+ `tests/test_signature_gate.py`), agent-zero `mcp_server.py`, and `services/common/` (branch_trail, geometry_decoder, model_fitness).

## Gated live path: dry-run vs shadow ledger

- Lane (settlement review §4.3): weekly `fordham-attribution.ts` **dry-run vs the PMOVES-Wealth shadow ledger** until accountant/counsel clear live settlement — MEASURED dependency probe: wealth-mcp :8092 listening (MCP streamable-http), 2026-10-05.
- Status: **the dry-run/shadow lane is defined and its dependencies probed; it is not live settlement, and no settlement results exist.** Any numbers shown in sims are sim outputs, labeled as such.
- Verification stack: `make -C pmoves sign-trail` closes the audit trail (dev mode emits unsigned with a stderr warning by design).

**Bottom line:** the theory now has a measured code artifact plus a gated live path. What's missing is signatures-by-default (G3), signed manifests (G4), and counsel clearance — not new math.
