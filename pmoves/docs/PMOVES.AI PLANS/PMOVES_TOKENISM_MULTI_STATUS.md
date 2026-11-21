# PMOVES-ToKenism-Multi — Status
_Last updated: 2026-11-06_

## Purpose

Cooperative economic simulation with verifiable attribution: a Python/Flask simulator models cooperative-vs-traditional wealth trajectories, and the resulting attribution is exported as CHIT geometry documents (CGP) onto the PMOVES.AI Geometry Bus (NATS) for downstream consumers (publisher-discord, Hi-RAG v2, Shape Store).

## Submodule Contract

- **Tracked branch:** `PMOVES.AI-Edition-Hardened` (matches this repo's `.gitmodules` entry)
- **Image builds:** `pmoves/images.yaml` builds container images from this repo; pushes to the hardened branch trigger automated GHCR builds
- **Integration contract:** `docs/CHIT_INTEGRATION.md` (added 2026-11-06, PR #68) — documents the four `tokenism.*` NATS subjects, payload schemas, AJV fail-closed validation, and parent-side consumers

## Implemented and Verified (as of 2026-11-06)

### Settlement / money path
- Real HMAC verification on the Firefly settlement path — `createHmac`/`timingSafeEqual` verifier with an alg registry, canonical domain-separated preimages, own-property proof reads (PR #65)
- Signed activation-pack fixtures against a real keyring; truthiness gates closed across the settlement lane

### Governance contracts
- Ed25519 multisig `TallySigner` with self-verifiable committee tally signatures; fail-closed on threshold/algo/key-material/hex (PR #62)
- Mode-A secret-ballot tally ingestion with ballotRef provenance binding and defensive copies (PR #63)
- `EqualWeightGovernor` — equal-weight tally, roll-% quorum, M-of-N finalize (PR #60)

### Test infrastructure (repaired 2026-11-06)
- Fixed silently-skipped Next.js suites: tsx `testMatch`, jsdom environment, ResizeObserver mock (PR #66) — suite went 19/155 → 103/155
- WCAG 2.1 AA accessibility contracts implemented for `ChartWrapper` (PR #66) and `EnhancedSimulationForm` (PR #67) — combined form suites 9/34 → **34/34**
- Reachability-based focus verification honoring WAI-ARIA tablist/tabpanel composite semantics

### Security posture
- `docs/DEPENDABOT_TRIAGE_2026-11-06.md` (PR #69): 292 open alerts decoded (13 critical, 136 high), per-package patched versions extracted, P0/P1 remediation waves defined (next, handlebars, basic-ftp are the critical tier)

## Test Status (verified locally)

| Suite | Result |
|---|---|
| Flask backend (pytest) | 52/52 pass |
| integrations Jest (contracts/money path) | 21/21 suites pass |
| pmoves-nextjs Jest (form + a11y) | 34/34 pass |

The parent's `submodule_test_matrix` pytest command passes against this branch.

## Open Work

1. **Dependency remediation waves** per `docs/DEPENDABOT_TRIAGE_2026-11-06.md` — `next` bump to 15.5.28+, `handlebars` override to 4.7.9+, `basic-ftp` 5.2.2; then per-manifest `npm audit fix` passes (~85% of alerts clear in two waves)
2. **Stage 4b governance design** — tiered verifiable tally + voter-card.v1 spec recovered at `docs/superpowers/specs/2026-08-02-stage-4b-unlinkability-design.md` (PR #66); implementation not started
3. **No-patch advisories:** `extract-zip` (high), `elliptic` (low) — risk-accept or remove dependency path
4. **Cleanup (deferred per user instruction):** ~22 verified-merged remote branches and repo clutter (logs, lighthouse artifacts, duplicate requirement files)

## Open PRs (2026-11-06)

| PR | Content |
|---|---|
| #66 | Test-infra repair + ChartWrapper a11y + stage-4b spec recovery |
| #67 | EnhancedSimulationForm a11y contract + reachability focus tests |
| #68 | `docs/CHIT_INTEGRATION.md` Geometry Bus contract |
| #69 | Dependabot triage + remediation plan |
