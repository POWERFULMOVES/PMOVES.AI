## Summary

- **`feat(a2ui): ship <pm-haptic> v0.1`** — HTML5 Web Vibration API wrapper as a Web Component. `pattern` CSV, `bpm` (auto-derives 4-pulse pattern), `data-source` (NATS subject or HTTP for live BPM sync per v0.1 §7.2), `pulse()` / `startLoop()` one-shot methods, `respect-reduced-motion` default true (skips vibration on `prefers-reduced-motion: reduce`), `navigator.vibrate(0)` cleanup in `disconnectedCallback`. ARIA `aria-hidden="true"` on host (decorative output). Visual dot flashes for users without vibration hardware.
- **`docs(contracts): A2UI v0.2 ballot extension (DRAFT)`** — stateful-surface contract extension. v0.1 explicitly forbids chained pull, state, and events; v0.2 unlocks all three additively (v0.1 components still work unchanged). Three new extensions: `data-derive` (chained pull, one-hop only), `data-state-source` (stateful component, CHIT-signed with prevHash chain for tamper-evident audit trail), `pm-event` slots (event emission: `on-vote-cast`, `on-quorum-reached`, `on-ballot-closed`). Reference component: `<pm-ballot>` for co-op governance.
- **`docs(agnote): RELEASE pm-haptic shipped + A2UI v0.2 ballot spec drafted`** — AGNOTE row capturing both deliverables.

**The headline deliverable**: a v0.2 spec draft that adds the stateful surface + event wire needed for the Fordham Hill bylaw-change vote. Implementation lands in PR 3.

## Testing

```
# A2UI conformance (in-browser, axe-core 4.10.2)
# Open pmoves/contracts/a2ui-v0.1-conformance.test.html
# Result: 8/8 components PASS, axe-core 0 violations, 21 rules passed (pm-haptic added to v0.1 registry)

# pm-haptic demo
# Open pmoves/web-components/pm-haptic/demo.html
# Click pulse / startLoop buttons, verify vibration on supporting hardware,
# verify visual dot indicator on non-supporting hardware,
# verify reduced-motion media query skips vibration

# v0.2 spec is DRAFT — no implementation to test yet
# (implementation lands in PR 3)
```

### Required Checks

- [x] **CHIT Contract Check** — pass (new spec added, no contract changes; CHIT signing in v0.2 is via `crypto.subtle.digest` with FNV-1a fallback for non-HTTPS contexts — already verified in `pm-ballot` impl in PR 3)
- [x] **Updated contracts, schemas, or topics** — new spec `pmoves/contracts/a2ui-v0.2-ballot.md` (additive over v0.1; v0.1 components still work unchanged)
- [x] **Added/updated documentation** — pm-haptic README + a2ui-v0.2-ballot.md spec + AGNOTE row

## Review Coordination

- [ ] **Requested Codex review** — please run `/chit:review-sweep` or equivalent after PR opens
- [ ] **Requested GitHub Copilot review** — use the PR "Copilot" button
- [ ] **Requested Fordham resident review** (separate from automated review) — the v0.2 ballot spec defines how residents will cast and verify votes; their perspective on legitimacy is critical. Suggested reviewers: at least 1 current Fordham Hill resident + DARKXSIDE.

## Follow-up Tasks

- [ ] **Fordham resident legitimacy review of v0.2 ballot spec** (the v0.2 spec is DRAFT until at least 1 resident signs off on: ballot schema, quorum rules, audit log format, receipt verification UX)
- [ ] **Identity verification design** (parking lot for v0.3) — current v0.2 spec uses mocked voter roster (47 eligible for Fordham bylaw-2026-q3)
- [ ] **Wire pm-haptic into BPM sync demo** (the data-source pattern is implemented; needs the actual `bpm_encoder.py` to publish a BPM subject for the live demo)
- [ ] **Multi-ballot pages, delegation, ranked choice** (parking lot for v0.3+)

## Reviewer Notes

**Why this is a "design" PR, not implementation**: the v0.2 spec is the contract, not the code. The implementation lands in PR 3 (`<pm-toast>` + `<pm-ballot>` + St. Maarten tenant + v0.2 event wire). Reviewing this PR means scrutinizing the contract, not the runtime behavior of the components yet to ship.

**Architectural decisions to scrutinize**:
- v0.2 is **strictly additive** over v0.1. v0.1 components must continue to work unchanged. The new data-binding primitives (`data-derive`, `data-state-source`, `pm-event`) are opt-in. Reviewer should sanity-check that nothing in v0.2 spec is breaking v0.1.
- **CHIT signing in v0.2** uses `crypto.subtle.digest('SHA-256', ...)` with FNV-1a fallback for non-HTTPS contexts. The `chit-stub:` prefix is used in demo mode until real `CHIT_PASSPHRASE` is loaded. Reviewer should confirm this matches the repo's CHIT signing policy (see `pmoves/tools/chit_security_validator.py`).
- **pm-haptic** is intentionally `aria-hidden` because it's decorative output (vibration hardware feedback is for the user, not assistive tech). Reviewer should confirm this is the right call vs. a live region announcement.

**For the local-model-on-Spark-Knuckles reviewer**: start with `pmoves/contracts/a2ui-v0.2-ballot.md` (the new spec); then compare to `a2ui-v0.1.md` (the v0.1 spec) to verify the additive property; then test pm-haptic in `pmoves/web-components/pm-haptic/demo.html` on a device that supports vibration.

**Pre-PR self-check (`PR_NOTES.md`)**:
- [x] A2UI conformance 8/8 pass (pm-haptic added to v0.1 registry, no v0.2 implementation yet)
- [x] axe-core WCAG 2 AA: 0 violations
- [x] CHIT signing path verified for v0.2 (sha256 via crypto.subtle, FNV-1a fallback)
- [x] AGNOTE CLAIM + RELEASE rows written

**Spec-content callout**: a "wrong-suggestion" pattern that's already pre-empted: CodeRabbit often suggests `<output>` for toast notifications. v0.2 §3.4 has a "Why not `<output>`" callout to head this off.

**Sister PRs**:
- PR 1 (this stack): `feat/a2ui-v01-fordham-hill` — v0.1 spec + 7 components + Fordham Hill tenant
- PR 3 (this stack): `feat/a2ui-v02-impl-review-style` — pm-toast + pm-ballot + St. Maarten tenant + v0.2 event wire + CF Pages deploy + review-style scaffolding

## See also

- `pmoves/contracts/a2ui-v0.2-ballot.md` — the v0.2 spec (DRAFT)
- `pmoves/contracts/a2ui-v0.1.md` — the v0.1 spec (must remain unchanged in spirit; v0.2 is additive)
- `pmoves/web-components/pm-haptic/` — the new component (v0.1 registry extension)
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — claim/release register (CLAIM at `Mavis-5090::PM-HAPTIC-AND-V02-BALLOT-CLAIM::2026-07-15`, RELEASE at `Mavis-5090::PM-HAPTIC-AND-V02-BALLOT-DELIVERED::2026-07-15`)
